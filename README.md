# Food Taste Profile Discovery System

## Objective
Given an unlabeled dataset of food items, design a system that can analyze a food's name and description to predict its taste profile. The five basic tastes to consider are:
  - salty
  - umami
  - sweet
  - sour
  - bitter

There is no ground truth data provided. The goal is to provide a score ranging from 0 to 1 _for each label_, and to select the most representative label.

For example, for "pizza slice":

```
name,description,best_label,salty,umami,sweet,sour,bitter
Pizza Slice,A slice from a baked dish...,umami,0.8,0.9,0.3,0.2,0.1
```

The initial dataset is provided in the file `data/food_items_unlabeled.csv`. It contains only the food name and its description.

## Approach
The core hypothesis is that a food's taste profile can be derived as a weighted average of its constituent ingredients and their preparation methods. The system works in two phases: first, building a comprehensive knowledge base, and second, using it to generate profiles.

### Phase 1: Knowledge Base Construction
Since no direct ingredient-to-taste dataset was available, I constructed one from the ground up. I scraped [FlavorDB2](https://cosylab.iiitd.edu.in/flavordb2/) to map ingredients to their constituent chemical compounds. I then used [ChemTastesDB](https://zenodo.org/records/5747393) to map these chemical compounds to their known taste profiles. The tastes of all molecules in an ingredient were aggregated to create a single 5-point taste vector. This resulted in a base knowledge base of 935 ingredients ([View Base Knowledge Base](/data/knowledge_base/knowledge_base_average.csv)). 

To account for how cooking alters tastes, an LLM (`mistralai/Mistral-Nemo-Instruct-2407`) was used to generate thousands of 'processed' variations for the base ingredients. This expanded the knowledge base to over 4,000 entries, adding profiles for ingredients like `cabbage_fermented` or `pork_cured` based on the chemical transformations involved ([View Expanded Knowledge Base](/data/knowledge_base_average_processed.csv)).

### Phase 2: Taste Profile Generation
With the knowledge base in place, I developed a three-step pipeline to generate the final taste profile for any food item.

1. **Ingredient Deconstruction**: An LLM analyzes the food's name and description to extract key ingredients. It also estimates the taste proporition for each ingredient. This recognizes that a small amount of a potent ingredient like wasabi can have a large impact on the final taste.
2. **Profile Calculation**: The system retrieves a 5-point taste vector for each extracted ingredient from the expanded knowledge base. It then calculates a weighted average based on the assigned taste proportions.
3. **LLM Fallbacl**: If an ingredient is not found in the knowledge base, an LLM generates a taste profile for that specific ingredient on the fly.

The entire end-to-end process can be found in the main project notebook: [workflow.ipynb](/src/notebooks/workflow.ipynb).

## Evaluation
I used two primary evaluation strategies to validate the intermediate knowledge base and the final output.

### Knowledge Base Audit (Qualitative)
I randomly sampled 5 base ingredients and their associated processing enhancements. This analysis confirmed the knowledge base's logical consistency. The model correctly identified that `sourdough` bread is more sour than `white_bread`, and that roasting vegetables increases `sweet` and `bitter` scores because of the Maillard reaction.

However, I also identified a key limitation. The model sometimes applies a general rule even when ingredient-specific knowledge contradicts it. For example, the model's note for `bittergourd_roasted` correctly stated that roasting reduces bitterness, but the generated score showed an increase in `bitter`. Moreover, the `bitter` score for `bittergourd` was quite low in the original knowledge base, highlighting potential issues with my molecule aggregation strategy.

### Final Output Validation (Quantitative)
An LLM-as-a-Judge was used to evaluate the final `best_label` for the 50 food items. The judge assigned a grade based on the label's quality: **A** (Accurate), **B** (Acceptable), **C** (Inaccurate), or **D** (No Dominant Taste).

I calculated two metrics:
- Strict Accuracy: The percentage of labels graded **A**
- Acceptable Accuracy: The percentage of labels graded **A** or **B**

## Results
The system achieved an Acceptable Accuracy of 78%. This implies that the proposed methodology produces a reasonable dominant taste label in a majority of the cases.

| Grade                         | Count |
|------------------------------|-------|
| Total Items Evaluated        | 50    |
| Grade 'A' (Accurate)         | 26    |
| Grade 'B' (Acceptable)       | 13    |
| Grade 'C' (Inaccurate)       | 11    |
| Grade 'D' (No Dominant)      | 0     |

| Accuracy Type                | Percentage |
|-----------------------------|------------|
| Strict Accuracy (A only)    | 52.00%     |
| Acceptable Accuracy (A + B) | 78.00%     |
