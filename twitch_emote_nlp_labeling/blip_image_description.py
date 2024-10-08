# -*- coding: utf-8 -*-
"""BLIP_image_description.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1oprdDTvelK666ItNkx7c93uvtbkxw8kn

# Context

We want a scalable solution to describing visually what a Twitch streaming channel's emotes look like. Right now, the emotes do not have descriptions accessible on the Twitch website or 3rd party websites either.

Thus, I plan to leverage using Salesforce's BLIP NLP model to provide labels, and use Beautiful Soup to scrape the HTML of the emote name and web URL off the Twitch emote sites, and then create a resulting CSV of the map between an emote name, and what it looks like visually.

This is done in an effort to give our LLMs more insight into what Twitch channel specific emotes (like Hasan Abi channel for example) with their own custom emotes that LLMs have not been trained on so we can provide an accurate decision about how the emote is being used in context with a respective chat message.

# Installation and Setup
"""

!pip install requests beautifulsoup4
!pip install playwright
!pip install nest_asyncio
!playwright install

"""# Beautiful Soup Emote URL Scraper"""

import json
import asyncio
import nest_asyncio
from playwright.async_api import async_playwright

# Apply the nest_asyncio fix to allow running asyncio within a Jupyter/Colab environment
nest_asyncio.apply()

# List of URLs to scrape
urls = [
    'https://twitchemotes.com/channels/207813352',  # Twitch emotes
    'https://betterttv.com/users/5be4ca273d3f791478f2e481'  # BetterTTV emotes
]

# List to store all emote data (URL and name)
emote_data = []

async def fetch_emotes(page, url):
    # Open the URL in the browser
    await page.goto(url)
    await page.wait_for_load_state('networkidle')  # Ensure the page fully loads

    # Find all the <img> tags containing emote images for Twitch
    if 'twitchemotes' in url:
        image_tags = await page.query_selector_all('img')

        # Extract the URLs and names of the emotes from Twitch
        for img in image_tags:
            src = await img.get_attribute('src')
            emote_name = await img.get_attribute('data-regex')  # Extract emote name from the data-regex attribute

            if src and emote_name and src.startswith('https://static-cdn.jtvnw.net/emoticons/v2/'):
                emote_data.append({
                    'url': src,
                    'name': emote_name
                })

    # Find all <img> tags containing emote images for BetterTTV
    elif 'betterttv' in url:
        div_tags = await page.query_selector_all('div')

        # Extract the URLs and names of the emotes from BetterTTV
        for div in div_tags:
            content = await div.evaluate('(element) => element.innerHTML')
             # Check if the div has the desired class
            class_name = await div.evaluate('(element) => element.className')

            # This is just what happened to be named the class,
            # I found this just by inspecting the elements on the HTML
            if 'chakra-container css-k5mm6t' in class_name:
                # If it matches, get all img tags within this div
                img_tags = await div.query_selector_all('img')

                # Extract the URLs and names of the emotes
                for img in img_tags:
                    src = await img.get_attribute('src')
                    emote_name = await img.get_attribute('alt')

                    if src and emote_name:
                        emote_data.append({
                            'url': src,
                            'name': emote_name
                        })

async def main():
    # Start Playwright and scrape emote data
    async with async_playwright() as p:
        # Launch browser in headless mode
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Fetch emotes for each URL
        for url in urls:
            await fetch_emotes(page, url)

        # Close the browser
        await browser.close()

    # Print the number of emotes found and the first few for verification
    print(f"Total emotes found: {len(emote_data)}")
    print(emote_data[:5])  # Preview first 5 emotes

    # Save the emote data to a JSON file
    with open('emote_data.json', 'w') as json_file:
        json.dump(emote_data, json_file, indent=4)

# Run the main function
await main()

"""# BLIP Image Caption Generator"""

import csv
import requests
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
import json

# Load the processor and model
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large")

# Load JSON file
with open('emote_data.json', 'r') as f:
    emote_data = json.load(f)

# Create the CSV file
with open('hasan_abi_channel_emote_text.csv', mode='w', newline='') as file:
    writer = csv.writer(file)
    # Note, here conditional means given context about what it is labeling, ie "an emote of a..."
    # unconditional would be the opposite, no context.
    writer.writerow(['emote_name', 'text_description_conditional', 'text_description_unconditional'])

    # Loop over each emote in the JSON
    for emote in emote_data:
        emote_name = emote['name']
        img_url = emote['url']
        print(emote_name)

        # Fetch the image
        try:
            raw_image = Image.open(requests.get(img_url, stream=True).raw).convert('RGB')

            # conditional image captioning
            text = "an emote showing "
            inputs = processor(raw_image, text, return_tensors="pt")

            out = model.generate(**inputs)
            text_description_conditional = processor.decode(out[0], skip_special_tokens=True)
            print(text_description_conditional)

            # Unconditional image captioning
            inputs = processor(raw_image, return_tensors="pt")
            out = model.generate(**inputs)
            text_description_unconditional = processor.decode(out[0], skip_special_tokens=True)
            print(text_description_unconditional)

            # Write the data to the CSV
            writer.writerow([emote_name, text_description_conditional, text_description_unconditional])

        except Exception as e:
            print(f"Error processing {emote_name}: {e}")