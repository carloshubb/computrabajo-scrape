import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

def scrape_computrabajo_job(url):
    """
    Scrape job posting data from Computrabajo
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Initialize data dictionary
        job_data = {
            'featured_image': None,
            'title': None,
            'featured': False,
            'filled': False,
            'urgent': False,
            'description': None,
            'category': None,
            'type': None,
            'tag': None,
            'expiry_date': None,
            'gender': None,
            'apply_type': None,
            'apply_url': None,
            'apply_email': None,
            'salary_type': None,
            'salary': None,
            'max_salary': None,
            'experience': None,
            'career_level': None,
            'qualification': None,
            'video_url': None,
            'photos': [],
            'application_deadline_date': None,
            'address': None,
            'location': None,
            'map_location': None,
            'company': None,
            'posted_date': None
        }
        
        # Extract title
        title_tag = soup.find('h1', class_='title_offer')
        if title_tag:
            job_data['title'] = title_tag.get_text(strip=True)
        
        # Extract company logo/featured image
        logo_img = soup.find('img', class_='logo')
        if logo_img and logo_img.get('src'):
            job_data['featured_image'] = logo_img['src']
        
        # Extract company name
        company_tag = soup.find('a', class_='fc_base')
        if company_tag:
            job_data['company'] = company_tag.get_text(strip=True)
        
        # Extract location
        location_tag = soup.find('p', class_='fs16 fc_base mt5')
        if location_tag:
            job_data['location'] = location_tag.get_text(strip=True)
            job_data['address'] = location_tag.get_text(strip=True)
        
        # Extract description
        desc_div = soup.find('div', class_='box_offer fs13')
        if desc_div:
            job_data['description'] = desc_div.get_text(strip=True)
        
        # Extract salary information
        salary_tag = soup.find('p', class_='fs16 fwB fc_base')
        if salary_tag:
            salary_text = salary_tag.get_text(strip=True)
            job_data['salary'] = salary_text
            # Try to parse min/max salary
            if '-' in salary_text:
                parts = salary_text.split('-')
                if len(parts) == 2:
                    job_data['salary'] = parts[0].strip()
                    job_data['max_salary'] = parts[1].strip()
        
        # Extract job details from the detail boxes
        detail_boxes = soup.find_all('div', class_='box_detail')
        for box in detail_boxes:
            label = box.find('span', class_='tag_color')
            value = box.find('span', class_='tag_color_value')
            
            if label and value:
                label_text = label.get_text(strip=True).lower()
                value_text = value.get_text(strip=True)
                
                if 'categoría' in label_text or 'category' in label_text:
                    job_data['category'] = value_text
                elif 'tipo' in label_text or 'type' in label_text:
                    job_data['type'] = value_text
                elif 'experiencia' in label_text or 'experience' in label_text:
                    job_data['experience'] = value_text
                elif 'estudios' in label_text or 'qualification' in label_text:
                    job_data['qualification'] = value_text
                elif 'publicad' in label_text or 'posted' in label_text:
                    job_data['posted_date'] = value_text
        
        # Check for featured/urgent badges
        badges = soup.find_all('span', class_='badge')
        for badge in badges:
            badge_text = badge.get_text(strip=True).lower()
            if 'destacad' in badge_text or 'featured' in badge_text:
                job_data['featured'] = True
            if 'urgent' in badge_text:
                job_data['urgent'] = True
        
        # Extract apply URL/button
        apply_btn = soup.find('a', class_='btn_application') or soup.find('button', class_='btn_application')
        if apply_btn:
            if apply_btn.get('href'):
                job_data['apply_url'] = apply_btn['href']
                job_data['apply_type'] = 'external' if 'http' in apply_btn['href'] else 'internal'
            else:
                job_data['apply_type'] = 'internal'
        
        # Extract email if present
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, response.text)
        if emails:
            job_data['apply_email'] = emails[0]
        
        # Extract images
        images = soup.find_all('img')
        for img in images:
            src = img.get('src')
            if src and 'logo' not in img.get('class', []):
                job_data['photos'].append(src)
        
        # Look for map/location data
        map_script = soup.find('script', string=re.compile('lat|lng|coordinates'))
        if map_script:
            # Try to extract coordinates from script
            coord_match = re.search(r'lat["\']?\s*:\s*([+-]?\d+\.?\d*)', map_script.string)
            if coord_match:
                job_data['map_location'] = coord_match.group(1)
        
        return job_data
        
    except Exception as e:
        print(f"Error scraping job: {str(e)}")
        return None

# Example usage
if __name__ == "__main__":
    url = "https://cr.computrabajo.com/ofertas-de-trabajo/oferta-de-trabajo-de-asistente-comercial-en-san-jose-DCF3BCB41ED4C14A61373E686DCF3405"
    
    print("Scraping job posting...")
    job_data = scrape_computrabajo_job(url)
    
    if job_data:
        print("\n" + "="*50)
        print("JOB DATA EXTRACTED")
        print("="*50)
        print(json.dumps(job_data, indent=2, ensure_ascii=False))
        
        # Save to JSON file
        with open('job_data.json', 'w', encoding='utf-8') as f:
            json.dump(job_data, f, indent=2, ensure_ascii=False)
        print("\nData saved to job_data.json")
    else:
        print("Failed to scrape job data")