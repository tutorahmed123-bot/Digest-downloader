import requests
from bs4 import BeautifulSoup
import os
import time
import base64
from PIL import Image
from tqdm import tqdm
import io
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_soup(url):
    try:
        # 30 second timeout to handle slow site responses
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 404:
            return "EOF" # Signal end of novel
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"\n[Connection Issue] {e}. Retrying in 5s...")
        time.sleep(5)
        return None

def main():
    # 1. Ask for input
    input_url = input("Enter the Novel URL (e.g. ...cat=201) or just the ID: ").strip()
    
    # Extract Category ID to organize folders
    cat_match = re.search(r'cat=(\d+)', input_url)
    cat_id = cat_match.group(1) if cat_match else input_url
    
    base_url = f"https://thisaccessories.com/reading-base/?cat={cat_id}"
    save_folder = f"novel_cat_{cat_id}"
    
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)

    # 2. Resume Logic: Check how many slices we already have
    existing_slices = sorted([f for f in os.listdir(save_folder) if f.endswith('.jpg')])
    current_page_num = (len(existing_slices) // 5) + 1
    
    print(f"\n--- Starting Scraper for Category: {cat_id} ---")
    print(f"Saving to: {save_folder}")
    print(f"Resuming from Web Page: {current_page_num}\n")

    try:
        while True:
            page_url = f"{base_url}&paged={current_page_num}"
            if current_page_num == 1: page_url = base_url

            soup = get_soup(page_url)
            if soup == "EOF":
                print(f"\nReached the end of the novel (404).")
                break
            if not soup: continue

            # Find images in the 'primary' content div
            content_area = soup.find('div', id='primary') or soup.body
            imgs = content_area.find_all('img')
            
            # Extract Base64 strings (the text that becomes an image)
            base64_data = [img.get('src') for img in imgs if img.get('src', '').startswith('data:image')]
            
            if not base64_data:
                print("No more images found on this page.")
                break

            # Save each slice (usually 5 per page)
            for i, data_string in enumerate(base64_data):
                slice_idx = ((current_page_num - 1) * 5) + i + 1
                file_path = os.path.join(save_folder, f"slice_{slice_idx:05d}.jpg")
                
                if not os.path.exists(file_path):
                    _, encoded = data_string.split(",", 1)
                    with open(file_path, 'wb') as f:
                        f.write(base64.b64decode(encoded))

            print(f"Done: Page {current_page_num}")
            current_page_num += 1
            time.sleep(0.5) # Politeness delay

    except KeyboardInterrupt:
        print("\nInterrupted. Building PDF from slices collected so far...")

    # 3. Gap-Free PDF Stitching
    all_slices = sorted([os.path.join(save_folder, f) for f in os.listdir(save_folder) if f.endswith('.jpg')])
    
    if not all_slices:
        print("No slices found to combine.")
        return

    print(f"\nStitching {len(all_slices)} slices into gap-free pages...")
    final_pages = []
    
    # Process slices in groups of 5 to reconstruct the full page
    for i in tqdm(range(0, len(all_slices), 5), desc="PDF Processing"):
        batch = all_slices[i:i+5]
        if len(batch) < 5: continue 
        
        imgs = [Image.open(f).convert('RGB') for f in batch]
        
        # Merge slices vertically with 0 pixels between them
        max_w = max(img.width for img in imgs)
        total_h = sum(img.height for img in imgs)
        combined_page = Image.new('RGB', (max_w, total_h))
        
        y_offset = 0
        for img in imgs:
            combined_page.paste(img, (0, y_offset))
            y_offset += img.height
            
        final_pages.append(combined_page)

    if final_pages:
        pdf_name = f"Novel_Cat_{cat_id}_Final.pdf"
        final_pages[0].save(pdf_name, save_all=True, append_images=final_pages[1:])
        print(f"\nSUCCESS! Created: {pdf_name}")
    else:
        print("Error: Could not assemble full pages (need at least 5 slices).")

if __name__ == "__main__":
    main()