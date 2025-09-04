"""
This script processes ingredient data from FlavorDB and taste classifications from ChemTastesDB to build a knowledge base. 
It aggregates molecule-level taste data into a single taste profile for each ingredient.
"""

import pandas as pd
import numpy as np
import json
from typing import Dict, List, Optional
from dataclasses import dataclass

# Configuration for different taste aggregation strategies
@dataclass
class AggregationConfig:
    method: str  # 'average', 'dominant', or 'threshold'
    threshold: float = 0.4
    flavor_profile_mapping: bool = True

class TasteAggregator:
    # Aggregates molecule-level taste data into ingredient-level profiles.
    
    def __init__(self, config: AggregationConfig, chemtastes_db: pd.DataFrame):
        self.config = config
        self.taste_dimensions = ['salty', 'umami', 'sweet', 'sour', 'bitter']
        
        db = chemtastes_db.copy()
        if 'PubChem CID' not in db.columns:
            raise KeyError("The required column 'PubChem CID' was not found in the ChemTastesDB file.")
        
        db.rename(columns={'PubChem CID': 'pubchem_cid', 'Class taste': 'class_taste'}, inplace=True)
        db['pubchem_cid'] = pd.to_numeric(db['pubchem_cid'], errors='coerce')
        
        # drop rows where the pubchem_cid is NaN
        db.dropna(subset=['pubchem_cid'], inplace=True)
        db['pubchem_cid'] = db['pubchem_cid'].astype(int)
        
        db.set_index('pubchem_cid', inplace=True)
        self.chemtastes_db_indexed = db

        # keyword mapping for converting flavor text to taste scores
        self.flavor_mappings = {
            'sweet': {'sweet', 'honey', 'caramel', 'vanilla', 'maple', 'sugary'},
            'salty': {'salty', 'briny', 'sea', 'ocean', 'saline'},
            'sour': {'sour', 'tart', 'acidic', 'citrus', 'vinegar', 'fermented'},
            'bitter': {'bitter', 'astringent', 'medicinal', 'alkaline', 'quinine'},
            'umami': {'meaty', 'savory', 'mushroom', 'cheese', 'nutty', 'roasted', 'beef', 'brothy', 'yeasty'}
        }
        # reverse map for faster lookups ({'keyword': 'taste_dimension'})
        self.keyword_to_taste = {
            keyword: taste 
            for taste, keywords in self.flavor_mappings.items() 
            for keyword in keywords
        }

    def _map_flavor_text_to_scores(self, flavor_profile: str) -> Dict[str, float]:
        # Map flavor profile text to taste scores.
        scores = {dim: 0.0 for dim in self.taste_dimensions}
        if not isinstance(flavor_profile, str):
            return scores

        profiles = {p.strip().lower() for p in flavor_profile.split('@') if p.strip()}
        
        for profile in profiles:
            if profile in self.keyword_to_taste:
                scores[self.keyword_to_taste[profile]] = 1.0
            else:
                for keyword, taste_dim in self.keyword_to_taste.items():
                    if keyword in profile:
                        scores[taste_dim] = max(scores[taste_dim], 0.8)
        return scores

    def get_molecule_taste_scores(self, molecule: Dict) -> Dict[str, float]:
        # getting 5D taste scores for a single molecule

        scores = {dim: 0.0 for dim in self.taste_dimensions}
        pubchem_id = molecule.get('pubchem_cid')

        if pubchem_id and pd.notna(pubchem_id):
            try:
                chem_row = self.chemtastes_db_indexed.loc[int(pubchem_id)]
                taste_class = chem_row['class_taste'].lower() if pd.notna(chem_row['class_taste']) else ''
                
                if 'sweet' in taste_class: scores['sweet'] = 1.0
                if 'bitter' in taste_class: scores['bitter'] = 1.0
                if 'sour' in taste_class: scores['sour'] = 1.0
                if 'salty' in taste_class: scores['salty'] = 1.0
                if 'umami' in taste_class: scores['umami'] = 1.0

            except KeyError:
                pass
        
        if self.config.flavor_profile_mapping:
            flavor_scores = self._map_flavor_text_to_scores(molecule.get('flavor_profile', ''))
            for dim in self.taste_dimensions:
                scores[dim] = max(scores[dim], flavor_scores[dim])
        
        return scores
    
    def aggregate_taste_scores(self, molecule_scores: List[Dict[str, float]]) -> Dict[str, float]:
        # aggregates scores from all molecules into a single ingredient profile.
        if not molecule_scores:
            return {dim: 0.0 for dim in self.taste_dimensions}
        
        df = pd.DataFrame(molecule_scores)
        
        if self.config.method == 'average':
            return df.mean().to_dict()
        elif self.config.method == 'dominant':
            return df.max().to_dict()
        elif self.config.method == 'threshold':
            return df[df >= self.config.threshold].mean().fillna(0).to_dict()
        
        return {dim: 0.0 for dim in self.taste_dimensions}
    
    def process_ingredient(self, ingredient_row: pd.Series) -> Dict[str, float]:
        # process a row from FlavorDB
        try:
            molecules_data = json.loads(ingredient_row['molecules'])
        except (json.JSONDecodeError, TypeError):
            return {dim: 0.0 for dim in self.taste_dimensions}

        molecule_scores = [self.get_molecule_taste_scores(mol) for mol in molecules_data]
        return self.aggregate_taste_scores(molecule_scores)

def create_knowledge_base(flavordb_path: str, chemtastes_path: str, config: AggregationConfig, output_path: str):
    # main workflow function
    print(f"--- Running with strategy: {config.method} ---")
    
    flavordb_df = pd.read_csv(flavordb_path)
    chemtastes_df = pd.read_excel(chemtastes_path)
   
    aggregator = TasteAggregator(config, chemtastes_df)
    
    print(f"Processing {len(flavordb_df)} ingredients")
    taste_profiles = flavordb_df.apply(aggregator.process_ingredient, axis=1, result_type='expand')
    
    kb_df = pd.concat([flavordb_df[['name', 'category', 'molecule_count']], taste_profiles], axis=1)
    
    kb_df.rename(columns={'name': 'entity_name'}, inplace=True)
    kb_df['entity_type'] = 'ingredient'
    kb_df['notes'] = "Category: " + kb_df['category'] + ", Molecules: " + kb_df['molecule_count'].astype(str)
    
    for dim in aggregator.taste_dimensions:
        kb_df[dim] = kb_df[dim].round(3)
        
    final_columns = ['entity_name', 'entity_type', 'salty', 'umami', 'sweet', 'sour', 'bitter', 'notes']
    kb_df = kb_df[final_columns]
    
    kb_df.to_csv(output_path, index=False)
    print(f"Knowledge base successfully saved to {output_path}")
    return kb_df

def main():    
    strategies = [
        AggregationConfig(method='average'),
        AggregationConfig(method='dominant'),  
        AggregationConfig(method='threshold', threshold=0.5),
    ]
    
    for config in strategies:
        kb = create_knowledge_base(
            flavordb_path='flavordb_knowledge_graph.csv',
            chemtastes_path='ChemTastesDB_database.xlsx',
            config=config,
            output_path=f'knowledge_base_{config.method}.csv'
        )


if __name__ == "__main__":
    main()