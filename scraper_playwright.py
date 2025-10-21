import asyncio
import pandas as pd
from playwright.async_api import async_playwright

# ---------- Helper ----------
async def safe_text(page, selector, attr=None, html=False):
    try:
        el = await page.query_selector(selector)
        if not el:
            return None
        if attr:
            return await el.get_attribute(attr)
        if html:
            return await el.inner_html()
        return (await el.inner_text()).strip()
    except:
        return None


# ---------- Step 1: Collect job links ----------
async def get_job_links(page):
    print("🔄 Opening page and loading jobs...")
    await page.goto("https://cr.computrabajo.com/empleos-en-san-jose", timeout=90000)
    await page.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(3)

    # Scroll gradually to load all job cards
    print("🔄 Scrolling...")
    for i in range(12):
        await page.mouse.wheel(0, 3000)
        await asyncio.sleep(1.5)

    # Wait for job cards to appear
    await page.wait_for_selector("article", timeout=20000)

    # Extract all job links
    job_links = set()
    job_cards = await page.query_selector_all("article a.js-o-link")
    if not job_cards:
        # Fallback selector if structure changed
        job_cards = await page.query_selector_all("article a[href*='/ofertas-de-trabajo/']")

    for el in job_cards:
        href = await el.get_attribute("href")
        if href:
            if href.startswith("/"):
                href = "https://cr.computrabajo.com" + href
            job_links.add(href)

    print(f"✅ Found {len(job_links)} job links.")
    return list(job_links)


# ---------- Step 2: Scrape job detail ----------
async def scrape_job_detail(page, url):
    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_selector("h1", timeout=15000)

        html_content = await page.content()

         # 1️⃣ Compute job_type first
        job_type = None
        spans = await page.query_selector_all("div.mbB span.tag.base.mb10")

        for el in spans:
            text = await el.text_content()
            if not text:
                continue
            text_lower = text.lower()
            
            if "tiempo completo" in text_lower or "full time" in text_lower:
                job_type = "tiempo completo"
                break
            elif "medio tiempo" in text_lower or "part time" in text_lower:
                job_type = "medio tiempo"
                break
            elif "remoto" in text_lower or "remote" in text_lower:
                job_type = "remoto"
                break
            
        career_level = None
        experience = None

        items = await page.query_selector_all("ul.disc.mbB li")
        
        for li in items:
            text = await li.inner_text()
            if not text:
                continue
            text_lower = text.lower()
            if "education" in text_lower or "Educación" in text_lower:
                career_level = text.strip()
            elif "experience" in text_lower or "de experiencia" in text_lower:
                experience = text.strip()
            print("1---------->",career_level)
            
        # 2️⃣ Now create the dictionary
        job = {
            "featured_image": await safe_text(page, "meta[property='og:image']", attr="content"),
            "title": await safe_text(page, "h1.fwB.fs24.mb5.box_detail.w100_m"),
            "featured": "destacado" in html_content.lower(),
            "filled": "cerrada" in html_content.lower(),
            "urgent": "urgente" in html_content.lower(),
            "description": await safe_text(page, "div.fs16.t_word_wrap") or await safe_text(page, ".desc"),
            "category": await safe_text(page, ".box_tags a") or await safe_text(page, "li[data-testid='job-category'] span"),
            "type": job_type,  # assign the value computed above
            "tag": "Costa Rica",
            "expiry_date": await safe_text(page, "li[data-testid='expiry-date'] span"),
            "gender": await safe_text(page, "li[data-testid='gender'] span"),
            "apply_type": "external",
            "apply_url": url,
            "apply_email": None,
            "salary_type": await safe_text(page, "li[data-testid='salary-type'] span"),
            "salary": await safe_text(page, "li[data-testid='salary'] span"),
            "max_salary": None,
            "experience": experience,
            "career_level": career_level,
            "qualification": await safe_text(page, "li[data-testid='qualification'] span"),
            "video_url": await safe_text(page, "iframe[src*='youtube']", attr="src"),
            "photos": [],
            "application_deadline_date": await safe_text(page, "li[data-testid='deadline'] span"),
            "address": await safe_text(page, "li[data-testid='address'] span"),
            "location": await safe_text(page, "li[data-testid='location'] span"),
            "map_location": await safe_text(page, "iframe[src*='google.com/maps']", attr="src"),
        }
        # Extract all image URLs
        imgs = await page.query_selector_all("img")
        for i in imgs:
            src = await i.get_attribute("src")
            if src and src.startswith("http"):
                job["photos"].append(src)

        return job

    except Exception as e:
        print(f"❌ Error scraping {url}: {e}")
        return None


# ---------- Step 3: Main ----------
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # 👀 Set to False for visual debug
        page = await browser.new_page()

        job_links = await get_job_links(page)

        if not job_links:
            print("⚠️ No job links found — check page structure or selectors.")
            await browser.close()
            return

        results = []
        for i, link in enumerate(job_links, start=1):
            print(f"[{i}/{len(job_links)}] Scraping: {link}")
            job = await scrape_job_detail(page, link)
            if job:
                results.append(job)
                print("✅ Scraped successfully.")
            await asyncio.sleep(2)

        await browser.close()

        if results:
            df = pd.DataFrame(results)
            df.to_csv("data/jobs.csv", index=False, encoding="utf-8-sig")
            print("🎉 Scraping complete! Saved to data/jobs.csv")
        else:
            print("⚠️ No job data extracted.")


# ---------- Run ----------
if __name__ == "__main__":
    asyncio.run(main())
