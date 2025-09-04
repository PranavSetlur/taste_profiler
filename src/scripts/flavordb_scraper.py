"""
This script scrapes FlavorDB2 to create an ingredient-level dataset. Each row represents one ingredient and contains a 'molecules' column, which has a list of information about a single molecule.
"""

import requests
import pandas as pd
import time
import logging
import json
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KnowledgeGraphScraper:
    # Scraper for FlavorDB2 to create an ingredient-level dataset with nested molecule information.

    def __init__(self):
        self.base_url = "https://cosylab.iiitd.edu.in/flavordb2/entities_json"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })

    def get_ingredient_json(self, entity_id: int) -> Optional[Dict]:
        # Get the raw JSON data for a single ingredient by its ID.
        try:
            response = self.session.get(self.base_url, params={'id': entity_id}, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data if data else None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for ingredient ID {entity_id}: {e}")
            return None
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON for ingredient ID {entity_id}.")
            return None

    def parse_ingredient_with_molecules(self, raw_data: Dict) -> Optional[Dict]:
        # parses raw ingredient JSON
        if not raw_data or not raw_data.get('entity_alias_readable'):
            return None

        # get molecule info
        molecules_list = []
        for molecule in raw_data.get('molecules', []):
            molecules_list.append({
                'pubchem_cid': molecule.get('pubchem_id'),
                'molecule_name': molecule.get('common_name'),
                'flavor_profile': molecule.get('flavor_profile', ''),
                'taste': molecule.get('taste', ''),
                'odor': molecule.get('odor', ''),
                'functional_groups': molecule.get('functional_groups', '')
            })
        
        ingredient_record = {
            'ingredient_id': raw_data.get('entity_id'),
            'name': raw_data.get('entity_alias_readable').lower(),
            'category': raw_data.get('category_readable', ''),
            'scientific_name': raw_data.get('natural_source_name', ''),
            'molecule_count': len(molecules_list),
            'molecules': molecules_list  # This will be a list of dictionaries
        }
        
        return ingredient_record

    def scrape_ingredients(self, target_count: int = 1000, start_id: int = 1) -> List[Dict]:
        # scrapes ingredients
        
        collected_ingredients = []
        current_id = start_id
        consecutive_failures = 0
        max_failures = 100

        logger.info(f"Starting scrape for {target_count} ingredients.")

        while len(collected_ingredients) < target_count and consecutive_failures < max_failures:
            raw_data = self.get_ingredient_json(current_id)

            if raw_data:
                parsed_data = self.parse_ingredient_with_molecules(raw_data)
                if parsed_data:
                    collected_ingredients.append(parsed_data)
                    consecutive_failures = 0
                    if len(collected_ingredients) % 25 == 0:
                        logger.info(f"Collected {len(collected_ingredients)}/{target_count} ingredients...")
                else:
                    consecutive_failures += 1
            else:
                consecutive_failures += 1
            
            current_id += 1
            time.sleep(0.1)

        logger.info(f"Scraping finished. Collected {len(collected_ingredients)} ingredients.")
        return collected_ingredients

    def save_to_csv(self, ingredients: List[Dict], filename: str = "flavordb_knowledge_graph.csv"):
        if not ingredients:
            logger.warning("Ingredient list is empty. Nothing to save.")
            return

        df = pd.DataFrame(ingredients)
        
        # convert the 'molecules' column from list of dicts into a JSON string
        df['molecules'] = df['molecules'].apply(json.dumps)
        
        try:
            df.to_csv(filename, index=False, encoding='utf-8')
            logger.info(f"Successfully saved {len(df)} ingredients to {filename}")
        except Exception as e:
            logger.error(f"Failed to save data to CSV: {e}")

def main():
    scraper = KnowledgeGraphScraper()
    logger.info("\n--- Starting full ingredient scrape ---")
    all_ingredients = scraper.scrape_ingredients(target_count=1000)

    if all_ingredients:
        scraper.save_to_csv(all_ingredients)
        
        # You can load it back to verify
        print("\n--- Verifying saved CSV file ---")
        df_loaded = pd.read_csv("flavordb_knowledge_graph.csv")
        print("Columns in saved file:", df_loaded.columns.tolist())
        print("First row's 'molecules' cell content (it's a JSON string):")
        print(df_loaded.loc[0, 'molecules'][:150] + '...') # Print first 150 chars

if __name__ == "__main__":
    main()