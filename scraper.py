import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta
import time

now = datetime.now()
default_deadline = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

class ComputrabajoScraper:
    def __init__(self):
        self.base_url = "https://cr.computrabajo.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        self.session = requests.Session()
    
    def scrape_all_pages(self, base_url, max_pages=None, max_jobs=None):
        """Scrape all pages with pagination
        
        Args:
            base_url: Starting URL
            max_pages: Maximum number of pages to scrape (None for unlimited)
            max_jobs: Maximum number of jobs to scrape (None for unlimited)
        """
        all_jobs = []
        page = 1
        consecutive_empty = 0
        
        while True:
            # Check if we've reached the job limit
            if max_jobs and len(all_jobs) >= max_jobs:
                print(f"\n✓ Reached maximum jobs limit ({max_jobs})")
                break
            
            if page == 1:
                url = base_url
            else:
                separator = '&' if '?' in base_url else '?'
                url = f"{base_url.split('#')[0]}{separator}p={page}"
            
            print(f"\n{'='*60}")
            print(f"Scraping Page {page}")
            print(f"{'='*60}")
            
            # Calculate how many more jobs we need
            jobs_remaining = None
            if max_jobs:
                jobs_remaining = max_jobs - len(all_jobs)
                print(f"Jobs remaining to scrape: {jobs_remaining}")
            
            jobs = self.scrape_job_listings(url, max_jobs_this_page=jobs_remaining)
            
            if not jobs:
                consecutive_empty += 1
                print(f"No jobs found on page {page}.")
                
                if consecutive_empty >= 2:
                    print("Reached end of available jobs.")
                    break
            else:
                consecutive_empty = 0
                all_jobs.extend(jobs)
                print(f"\nTotal jobs scraped so far: {len(all_jobs)}")
            
            if max_pages and page >= max_pages:
                print(f"\nReached maximum pages limit ({max_pages})")
                break
            
            page += 1
            time.sleep(2)
        
        return all_jobs
    
    def has_next_page(self, url):
        """Check if there's a next page available"""
        return True
    
    def scrape_job_listings(self, url, max_jobs_this_page=None):
        """Scrape job listings from the main page
        
        Args:
            url: Page URL to scrape
            max_jobs_this_page: Maximum jobs to scrape from this page (None for all)
        """
        print(f"Fetching: {url}")
        try:
            response = self.session.get(url, headers=self.headers, timeout=30)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.content, 'html.parser')
            
            jobs = []
            job_cards = []
            
            job_cards = soup.find_all('article')
            
            if not job_cards:
                job_cards = soup.find_all('div', class_=re.compile('job|offer|card|box', re.I))
            
            if not job_cards:
                all_links = soup.find_all('a', href=re.compile('/ofertas-de-trabajo/'))
                job_cards = [link.find_parent(['article', 'div']) for link in all_links if link.find_parent(['article', 'div'])]
                job_cards = list({id(card): card for card in job_cards if card}.values())
            
            # Limit job cards if max specified
            if max_jobs_this_page:
                job_cards = job_cards[:max_jobs_this_page]
            
            print(f"Found {len(job_cards)} job cards on listing page")
            
            successful = 0
            skipped = 0
            
            for idx, card in enumerate(job_cards, 1):
                job_url = self.get_job_url(card)
                
                if job_url:
                    print(f"\nProcessing job {idx}/{len(job_cards)}...")
                    try:
                        job_data = self.scrape_job_details(job_url, card)
                        jobs.append(job_data)
                        successful += 1
                        time.sleep(1)
                    except Exception as e:
                        print(f"Error scraping job {idx}: {e}")
                        skipped += 1
                        continue
                else:
                    print(f"\nSkipping job {idx}/{len(job_cards)} - No URL found")
                    skipped += 1
            
            print(f"\nSummary: {successful} successful, {skipped} skipped")
            return jobs
        except Exception as e:
            print(f"Error fetching job listings: {e}")
            return []
    
    def get_job_url(self, card):
        """Extract job detail URL from card"""
        link = card.find('a', href=re.compile('/ofertas-de-trabajo/'))
        if link:
            href = link.get('href', '')
            full_url = self.base_url + href if href.startswith('/') else href
            return full_url.split('#')[0]
        
        link = card.find('a', href=True)
        if link:
            href = link.get('href', '')
            if '/ofertas-de-trabajo/' in href or '/trabajo/' in href:
                full_url = self.base_url + href if href.startswith('/') else href
                return full_url.split('#')[0]
        
        all_links = card.find_all('a', href=True)
        for link in all_links:
            href = link.get('href', '')
            if 'oferta' in href.lower() or 'trabajo' in href.lower():
                full_url = self.base_url + href if href.startswith('/') else href
                return full_url.split('#')[0]
        
        return None
    
    def scrape_job_details(self, job_url, card):
        """Scrape detailed information from individual job page"""
        print(f"Fetching details from: {job_url}")
        
        response = self.session.get(job_url, headers=self.headers, timeout=30)
        response.encoding = 'utf-8'
        detail_soup = BeautifulSoup(response.content, 'html.parser')
        
        job = {
            '_job_featured_image': self.get_featured_image(detail_soup),
            '_job_title': self.get_title(detail_soup, card),
            '_job_featured': '1' if self.is_featured(card) else '0',
            '_job_filled': '1' if self.is_filled(detail_soup) else '0',
            '_job_urgent': '1' if self.is_urgent(card) else '0',
            '_job_description': self.get_description(detail_soup),
            '_job_category': self.get_category(detail_soup),
            '_job_type': self.get_type(detail_soup),
            '_job_tag': 'Costa Rica',
            '_job_expiry_date': default_deadline,
            '_job_gender': self.get_gender(detail_soup),
            '_job_apply_type': 'external',
            '_job_apply_url': job_url,
            '_job_apply_email': self.get_apply_email(detail_soup),
            '_job_salary_type': self.get_salary_type(detail_soup),
            '_job_salary': self.get_salary(detail_soup, card),
            '_job_max_salary': self.get_max_salary(detail_soup, card),
            '_job_experience': self.get_experience(detail_soup),
            '_job_career_level': self.get_career_level(detail_soup),
            '_job_qualification': self.get_qualification(detail_soup),
            '_job_video_url': self.get_video_url(detail_soup),
            '_job_photos': ','.join(self.get_photos(detail_soup)),
            '_job_application_deadline_date': default_deadline,
            '_job_address': self.get_address(detail_soup,card),
            '_job_location': self.get_location(detail_soup, card),
            '_job_map_location': self.get_map_location(detail_soup),
        }
        
        return job
    
    def get_featured_image(self, soup):
        """Get company logo or featured image"""
        img = soup.find('img', class_=re.compile('logo|company'))
        if not img:
            img = soup.find('img', alt=re.compile('logo|empresa', re.I))
        return img.get('src', '') if img else ''
    
    def get_title(self, soup, card):
        """Get job title"""
        title = soup.find('h1')
        if not title:
            title = card.find(['h2', 'h3', 'a'])
        return title.text.strip() if title else ''
    
    def is_featured(self, card):
        """Check if job is featured/highlighted"""
        return 'destacado' in str(card).lower() or bool(card.find(string=re.compile('destacado', re.I)))
    
    def is_filled(self, soup):
        """Check if position is filled"""
        return bool(soup.find(string=re.compile('cubierta|ocupada', re.I)))
    
    def is_urgent(self, card):
        """Check if job is urgent"""
        urgent = card.find(string=re.compile('Se precisa Urgente|Urgente', re.I))
        return bool(urgent)
    
    def get_description(self, soup):
        """Get job description with clean paragraph and list formatting using \n\n."""
        import copy
        import re

        # Find main description container
        desc_heading = soup.find(['h2', 'h3'], string=re.compile('Descripción de la oferta', re.I))
        desc_container = None
        if desc_heading and hasattr(desc_heading, 'find_next'):
            try:
                desc_container = desc_heading.find_next('div')
            except Exception:
                desc_container = None

        if desc_container:
            desc_clone = copy.copy(desc_container)

            # Remove salary or metadata text
            salary_patterns = [
                r'₡', r'\d{1,3}[\s,]?\d{3}[\s,]?\d{2,3}',
                r'\(Mensual\)', r'\(Anual\)', r'\(Por hora\)',
                r'\+ Comisiones', r'A convenir', r'Salario\s*:'
            ]
            metadata_keywords = [
                'Tiempo Completo', 'Medio Tiempo', 'Temporal', 'Por horas',
                'Contrato por tiempo indefinido', 'Contrato temporal', 'Contrato por obra'
            ]

            for element in desc_clone.find_all(['span', 'div', 'p', 'strong', 'b']):
                elem_text = element.get_text(strip=True)
                if any(re.search(pattern, elem_text, re.I) for pattern in salary_patterns):
                    element.decompose()
                    continue
                if any(keyword.lower() in elem_text.lower() for keyword in metadata_keywords):
                    if len(elem_text) < 100:
                        element.decompose()

            # Extract full text from container
            text = desc_clone.get_text(" ", strip=True)

            # Put each numbered item (1., 2., etc.) onto its own line
            text = re.sub(r'\s*(?=\d+\.\s*)', '\n', text)

            # Section headers on new lines
            section_keywords = [
                'Requisitos:', 'Requerimientos:', 'Se ofrece:', 'Ofrecemos:',
                'Aportar:', 'Funciones:', 'Responsabilidades:'
            ]
            for kw in section_keywords:
                text = re.sub(r'\s*' + re.escape(kw), f'\n{kw}', text, flags=re.I)

            # Format bullet points
            text = re.sub(r'\s*-\s*', '\n- ', text)

            # Add paragraph breaks between sentences
            text = re.sub(r'([.!?])\s+(?=[A-ZÁÉÍÓÚ])', r'\1\n', text)

            # Clean up line breaks
            text = re.sub(r'\n{3,}', '\n', text)
            text = re.sub(r'\n{2,}(?=\d+\.)', '\n', text)

            # Remove salary patterns
            for pattern in salary_patterns:
                text = re.sub(pattern, '', text, flags=re.I)

            # Normalize spaces
            text = re.sub(r'[ \t]+', ' ', text)
            text = text.strip()

            if len(text) > 50:
                # Remove number prefixes but keep the structure and formatting
                lines = text.splitlines()
                cleaned_lines = []
                
                for line in lines:
                    line = line.strip()
                    if line:
                        # Remove number prefix if it exists (1. 2. 3. etc.)
                        cleaned_line = re.sub(r'^\d+\.\s*', '', line)
                        cleaned_lines.append(cleaned_line)
                
                # Join lines with double newlines to create clear paragraph breaks
                return '\n\n'.join(cleaned_lines)

        # Fallback: any long paragraph
        for p in soup.find_all('p'):
            t = p.get_text(" ", strip=True)
            if len(t) > 100 and '₡' not in t and not re.search(r'\d{3}[\s,]\d{3}', t):
                t = re.sub(r'\s*-\s*', '\n- ', t)
                t = re.sub(r'([.!?])\s+', r'\1\n\n', t)
                return t.strip()

        return ''
        
    def get_category(self, soup):
        """Get job category"""
        sidebar = soup.find('div', class_=re.compile('box-new|right|side|panel', re.I))
        if sidebar:
            category_tag = sidebar.find(['h2', 'h3', 'h4'])
            if category_tag:
                category = category_tag.get_text(strip=True)
                category = re.sub(r'\s*-.*$', '', category)
                if category and len(category) < 100:
                    return category
        
        location_patterns = ['San José', 'Heredia', 'Cartago', 'Alajuela', 'Guanacaste', 'Puntarenas', 'Limón']
        for pattern in location_patterns:
            location_elem = soup.find(string=re.compile(pattern, re.I))
            if location_elem:
                parent = location_elem.find_parent(['div', 'section'])
                if parent:
                    category_elem = parent.find_previous(['h2', 'h3', 'h4']) or parent.find(['h2', 'h3', 'h4'])
                    if category_elem:
                        category = category_elem.get_text(strip=True)
                        if category and len(category) < 100:
                            return category
        
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)
            category = re.split(r'\s*[-/]\s*(?:Sala|en|para)', title)[0].strip()
            return category
        
        return ''
    
    def get_type(self, soup):
        """Get employment type"""
        type_text = soup.find(string=re.compile('Tiempo Completo|Medio Tiempo|Temporal|Por horas', re.I))
        if type_text:
            return type_text.strip()
        
        contract = soup.find(string=re.compile('Contrato por tiempo indefinido|Contrato temporal', re.I))
        return contract.strip() if contract else ''
    
    def get_tags(self, card):
        """Get job tags"""
        tags = []
        if self.is_featured(card):
            tags.append('destacado')
        if self.is_urgent(card):
            tags.append('urgente')
        return tags
    
    def get_expiry_date(self, soup):
        """Get job expiry/update date"""
        updated = soup.find(string=re.compile(r'Hace.*actualizada', re.I))
        return updated.strip() if updated else ''
    
    def get_gender(self, soup):
        """Get gender requirements"""
        gender = soup.find(string=re.compile('Hombres|Mujeres|Indistinto', re.I))
        return gender.strip() if gender else ''
    
    def get_apply_email(self, soup):
        """Get application email"""
        email_link = soup.find('a', href=re.compile('^mailto:'))
        return email_link.get('href', '').replace('mailto:', '') if email_link else ''
    
    def get_salary_type(self, soup):
        """Determine salary type"""
        salary_text = self.get_salary(soup, None)
        if 'mensual' in salary_text.lower():
            return 'mensual'
        elif 'hora' in salary_text.lower():
            return 'hora'
        elif 'anual' in salary_text.lower():
            return 'anual'
        return 'mensual'
    
    def get_salary(self, soup, card):
        salary_text = soup.find(string=re.compile(r'A convenir|₡'))
        if salary_text:
            clean_salary = re.sub(r'\(.*?\)', '', salary_text)
            clean_salary = clean_salary.strip()
            return clean_salary
        return ''
    
    def get_max_salary(self, soup, card):
        salary_text = soup.find(string=re.compile(r'A convenir|₡'))
        if salary_text:
            clean_salary = re.sub(r'\(.*?\)', '', salary_text)
            clean_salary = clean_salary.strip()
            return clean_salary
        return ''
        
    def get_experience(self, soup):
        """Get required experience"""
        exp = soup.find(string=re.compile(r'\d+\s*año.*de experiencia', re.I))
        if exp:
            return exp.strip()
        
        req_section = soup.find(string=re.compile('Requerimientos|Requisitos', re.I))
        if req_section:
            parent = req_section.find_parent()
            if parent:
                exp_item = parent.find(string=re.compile('experiencia', re.I))
                if exp_item:
                    return exp_item.strip()
        return ''
    
    def get_career_level(self, soup):
        """Get career level"""
        level = soup.find(string=re.compile('Junior|Senior|Gerencial|Practicante', re.I))
        return level.strip() if level else ''
    
    def get_qualification(self, soup):
        """Get education requirements"""
        edu = soup.find(string=re.compile('Educación mínima:|Bachillerato|Universidad|Educación Media', re.I))
        if edu:
            parent = edu.find_parent()
            if parent:
                return parent.get_text(strip=True)
        return ''
    
    def get_video_url(self, soup):
        """Get video URL if exists"""
        video = soup.find('iframe', src=re.compile('youtube|vimeo'))
        return video.get('src', '') if video else ''
    
    def get_photos(self, soup):
        """Get job photos"""
        photos = []
        img_gallery = soup.find_all('img', class_=re.compile('gallery|photo'))
        for img in img_gallery:
            src = img.get('src', '')
            if src and 'logo' not in src.lower():
                photos.append(src)
        return photos
    
    def get_address(self, soup, card):
        """Extract clean city name"""
        text = ''

        p_tag = soup.find('p', class_='fs16')
        if p_tag:
            candidate = p_tag.get_text(strip=True)
            if re.search(r'(San José|Heredia|Cartago|Alajuela|Guanacaste|Puntarenas|Limón)', candidate, re.I):
                text = candidate

        if not text and card:
            loc_elem = card.find(string=re.compile(r'(San José|Heredia|Cartago|Alajuela|Guanacaste|Puntarenas|Limón)', re.I))
            if loc_elem:
                text = loc_elem.strip()

        if text:
            if len(text.split()) > 6 or re.search(r'\b(para|de|en|con|por|sector)\b', text, re.I):
                match = re.search(r'(San José|Heredia|Cartago|Alajuela|Guanacaste|Puntarenas|Limón)', text, re.I)
                if match:
                    return match.group(1).strip()
                else:
                    return ''

            if ',' in text:
                return text.split(',')[0].strip()

            return text.strip()

        return ''
        
    def get_location(self, soup, card):
        return self.get_address(soup, card)
    
    def get_map_location(self, soup):
        """Get Google Maps link"""
        map_link = soup.find('a', href=re.compile(r'maps\.google|goo\.gl'))
        return map_link.get('href', '') if map_link else ''
    
    def save_to_json(self, jobs, filename='jobs_computrabajo.json'):
        """Save scraped data to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
        print(f"\n✓ Saved {len(jobs)} jobs to {filename}")
    
    def save_to_csv(self, jobs, filename='jobs_computrabajo.csv'):
        """Save scraped data to CSV file"""
        import csv
        
        if not jobs:
            print("No jobs to save")
            return
        
        fieldnames = set()
        for job in jobs:
            fieldnames.update(job.keys())
        
        fieldnames = sorted(list(fieldnames))
        
        try:
            with open(filename, 'w', encoding='utf-8-sig', newline='', errors='replace') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for job in jobs:
                    writer.writerow(job)
            
            print(f"✓ Saved {len(jobs)} jobs to {filename}")
        except Exception as e:
            print(f"Error saving CSV: {e}")
            print("Trying alternative method...")
            with open(filename, 'w', encoding='utf-8-sig', errors='replace') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for job in jobs:
                    writer.writerow(job)
            
            print(f"✓ Saved {len(jobs)} jobs to {filename}")

# Usage
if __name__ == "__main__":
    scraper = ComputrabajoScraper()
    base_url = "https://cr.computrabajo.com/empleos-en-san-jose"
    
    print("=" * 60)
    print("Computrabajo Job Scraper - Automatic Mode")
    print("Scraping 200 jobs from San Jose, Costa Rica")
    print("=" * 60)
    print(f"\nStart time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Automatically scrape exactly 200 jobs
    jobs = scraper.scrape_all_pages(base_url, max_jobs=200)
    
    print("\n" + "=" * 60)
    print(f"✓ Scraping completed!")
    print(f"✓ Total jobs scraped: {len(jobs)}")
    print(f"✓ End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    if jobs:
        scraper.save_to_json(jobs)
        scraper.save_to_csv(jobs)
        
        print("\n" + "=" * 60)
        print("Sample Job Data (First Job):")
        print("=" * 60)
        print(json.dumps(jobs[0], indent=2, ensure_ascii=False))
        
        print("\n" + "=" * 60)
        print("Files created:")
        print("  - jobs_computrabajo.json")
        print("  - jobs_computrabajo.csv")
        print("=" * 60)
    else:
        print("\n⚠ No jobs found. Please check the URL or HTML structure.")