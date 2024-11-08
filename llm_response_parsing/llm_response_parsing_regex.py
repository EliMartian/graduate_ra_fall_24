# -*- coding: utf-8 -*-
"""LLM Response Parsing + Regex.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1blMEP9XOD0zLr3KCeHf-OOtpG3ZIkxbD

# LLM Parsing

**Motivation:** we want to be able to parse out the toxicity label (yes / no) and the associated toxicity category from poorly formed LLM JSON responses. And to make this more modular and re-usable, the following function is defined to handle different JSON files associated with different prompt instructions to the LLM. The resulting .csv output file contains correctly formatted and standardized data.
"""

import pandas as pd
import json
import re

# Processes the LLM data to parse out the response into a standardized and processed
# form to determine the overall toxic label for a Twitch chat message, and the associated
# toxic categories for the chat (if any)
def process_toxicity_data(input_csv, llama_json, zephyr_json, output_csv):
    # Load the CSV into a DataFrame (uses encoding for formatting / punctuation errors)
    df = pd.read_csv(input_csv, encoding='ISO-8859-1')

    # Loads the JSON data from the corresponding Llama and Zephyr LLM response file
    # Files are about ~200,000 rows in length
    with open(llama_json, 'r') as f:
        data_llama = json.load(f)

    with open(zephyr_json, 'r') as f:
        data_zephyr = json.load(f)

    # Extracts the "Is it toxic" attribute from LLM responses
    # (ie toxic label, but we use first attribute since the structure of json data can be malformed)
    def extract_first_attribute(conversation):
        assistant_content = conversation[2]["content"]

        # Check if the content is malformed with nested 'content' field
        if isinstance(assistant_content, dict) and 'content' in assistant_content:
            nested_content = assistant_content['content']
            # first try to filter on the is it toxic attribute that it was supposed to create in its LLM response
            match_no = re.search(r'"Is it toxic": "no"', nested_content, re.IGNORECASE)
            match_yes = re.search(r'"Is it toxic": "yes"', nested_content, re.IGNORECASE)
            # otherwise, if the LLM response malformed, then search for the assistant piece
            # where it contains its malformed response
            match_malformed = re.search(r'<\|assistant\|>\s*(.*)', nested_content, re.DOTALL)

            if match_no:
                return 'no'
            elif match_yes:
                return 'yes'
            elif match_malformed:
                body_response = match_malformed.group(1).lower()
                if ("non-toxic" in body_response or
                    "not toxic" in body_response or
                    "not flagged as toxic" in body_response):
                    return "no"
                elif "toxic" in body_response:
                    return "yes"
                else:
                    return 'none'
        if isinstance(assistant_content, dict):
            # if this is a map like we expect, we can parse out the toxic label easily
            first_key = list(assistant_content.keys())[0]
            return assistant_content[first_key]

        return 'none'

    # Extracts the second attribute from LLM responses
    # (ie toxic category, but we use second attribute since the structure of the json data can be malformed)
    def extract_second_attribute(conversation):
        assistant_content = conversation[2]["content"]

        if isinstance(assistant_content, dict) and 'content' in assistant_content:
            nested_content = assistant_content['content']
            match_no = re.search(r'"Is it toxic": "no"', nested_content, re.IGNORECASE)
            match_malformed = re.search(r'<\|assistant\|>\s*(.*)', nested_content, re.DOTALL)

            if match_no:
                return 'none'
            elif match_malformed:
                body_response = match_malformed.group(1).lower()
                if ("non-toxic" in body_response or
                    "not toxic" in body_response):
                    return "none"

                # define a list of categories to append to
                categories = []
                # some categories like obscen are misspelled intentionally, since the LLM
                # can say obscene or obscentity, which differ in the character folloiwing 'n',
                # hence the intentional misspell to capture the proper range of values
                if "insult" in body_response:
                    categories.append("insult")
                if "obscen" in body_response:
                    categories.append("obscene")
                if "sexual" in body_response:
                    categories.append("sexual_explicit")
                if "identity" in body_response:
                    categories.append("identity_attack")
                if "threat" in body_response:
                    categories.append("threat")

                return ", ".join(categories)

        if isinstance(assistant_content, dict):
            # if this is a map like we expect, we can parse out the toxic categories easily
            keys = list(assistant_content.keys())
            if len(keys) >= 2:
                second_key = keys[1]
                return assistant_content[second_key]

        return 'none'

    # Extract the first attribute values (ie toxic label, but we use first attribute since the structure of json data can be malformed)
    first_attribute_values_llama = [extract_first_attribute(conversation) for conversation in data_llama]
    first_attribute_values_zephyr = [extract_first_attribute(conversation) for conversation in data_zephyr]

    # Extract the second attribute values (ie toxic category, but we use second attribute since the structure of the json data can be malformed)
    second_attribute_values_llama = [extract_second_attribute(conversation) for conversation in data_llama]
    second_attribute_values_zephyr = [extract_second_attribute(conversation) for conversation in data_zephyr]

    toxic_df = pd.DataFrame()
    toxic_df['Llama Label'] = first_attribute_values_llama
    toxic_df['Llama Category'] = second_attribute_values_llama
    toxic_df['Zephyr Label'] = first_attribute_values_zephyr
    toxic_df['Zephyr Category'] = second_attribute_values_zephyr

    # Normalize labels and categories, including things such as removing puncuation and ensuring lower case responses
    # for standardization. Also, setting the LLM category or label to be none if it is not one that we support,
    # which can be commented out depending on use case.
    toxic_df['Zephyr Label'] = toxic_df['Zephyr Label'].str.lower().replace({'no': 'no', 'yes': 'yes'})
    toxic_df['Llama Label'] = toxic_df['Llama Label'].str.lower().replace({'no': 'no', 'yes': 'yes'})
    toxic_df['Zephyr Category'] = toxic_df['Zephyr Category'].str.replace(r"['\"\[\]]", '', regex=True).str.lower()
    toxic_df['Llama Category'] = toxic_df['Llama Category'].str.replace(r"['\"\[\]]", '', regex=True).str.lower()

    toxic_df.loc[~toxic_df['Zephyr Category'].isin(['insult', 'obscene', 'sexual_explicit', 'threat', 'identity_attack']), 'Zephyr Category'] = 'none'
    toxic_df.loc[~toxic_df['Llama Category'].isin(['insult', 'obscene', 'sexual_explicit', 'threat', 'identity_attack']), 'Llama Category'] = 'none'
    toxic_df.loc[~toxic_df['Zephyr Label'].isin(['yes', 'no', 'none']), 'Zephyr Label'] = 'none'
    toxic_df.loc[~toxic_df['Llama Label'].isin(['yes', 'no', 'none']), 'Llama Label'] = 'none'

    # Combine with the original DataFrame
    df['Zephyr Vanilla_E Label'] = toxic_df['Zephyr Label']
    df['Zephyr Vanilla_E Category'] = toxic_df['Zephyr Category']
    df['Llama Vanilla_E Label'] = toxic_df['Llama Label']
    df['Llama Vanilla_E Category'] = toxic_df['Llama Category']

    # Save the updated DataFrame to a new CSV file
    df.to_csv(output_csv, index=False)
    print(f"Processed data saved to '{output_csv}'.")

process_toxicity_data('toxicity_labels_full.csv', 'elias-llama-full-output-v_e.json', 'elias-zephyr-full-output-v_e.json', 'toxicity_labels_full_v_e.csv')
process_toxicity_data('toxicity_labels_full_v_e.csv', 'elias-llama-full-output-v.json', 'elias-zephyr-full-output-v.json', 'toxicity_labels_full_v.csv')
process_toxicity_data('toxicity_labels_full_v.csv', 'elias-llama-full-output-cot.json', 'elias-zephyr-full-output-cot.json', 'toxicity_labels_full_cot.csv')
process_toxicity_data('toxicity_labels_full_cot.csv', 'elias-llama-full-output-cot_e.json', 'elias-zephyr-full-output-cot_e.json', 'toxicity_labels_full_cot_e.csv')