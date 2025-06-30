import os
import json

# With this script, we split up the devset into single json files per review 
# in order to then be able to put each review seperatly into our pipeline
# The single json files are saved in the "devset_data" folder


input_file = './reviews_devset.json'
output_dir = './devset_data'

# Create output directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

with open(input_file, 'r', encoding='utf-8') as infile:
    for idx, line in enumerate(infile):
        try:
            review = json.loads(line)
            # Make a unique, compact, and filesystem-safe filename
            reviewer_id = review.get('reviewerID', 'unknown')
            asin = review.get('asin', 'unknown')
            # Remove any characters that could break file naming
            safe_reviewer = "".join(c for c in reviewer_id if c.isalnum())
            safe_asin = "".join(c for c in asin if c.isalnum())
            filename = f"review_{idx:06d}_{safe_reviewer}_{safe_asin}.json"
            outpath = os.path.join(output_dir, filename)
            # Save the review as a JSON file, pretty-printed
            with open(outpath, 'w', encoding='utf-8') as outfile:
                json.dump(review, outfile, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error on line {idx}: {e}")
