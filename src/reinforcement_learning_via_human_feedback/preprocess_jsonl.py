import json

# Define a function to process the JSONL content
def process_jsonl_content(jsonl_content):
    processed_entries = []
    seen_responses = set()

    for line in jsonl_content.strip().split('\n'):
        try:
            # Parse the JSON line
            entry = json.loads(line.strip())

            # Validate the structure
            if 'messages' not in entry or 'label' not in entry:
                print("Skipping invalid entry: Missing 'messages' or 'label'")
                continue

            # Ensure 'messages' contains valid roles
            for message in entry['messages']:
                if 'role' not in message or 'content' not in message:
                    print("Skipping invalid entry: Invalid message structure")
                    continue

            # Clean assistant responses if needed
            for message in entry['messages']:
                if message['role'] == 'assistant':
                    content = message['content']
                    if isinstance(content, str) and content.startswith("{'response':"):
                        try:
                            # Extract only the 'response' value
                            response_data = eval(content)  # Convert string to dictionary safely
                            message['content'] = response_data.get('response', content)
                        except Exception as e:
                            print(f"Error parsing response content: {e}")

            # Check for duplicate entries
            entry_hash = json.dumps(entry, sort_keys=True)
            if entry_hash in seen_responses:
                print("Skipping duplicate entry")
                continue
            seen_responses.add(entry_hash)

            # Append the cleaned entry to the processed entries
            processed_entries.append(entry)

        except json.JSONDecodeError as e:
            print(f"Skipping invalid JSON line: {e}")

    print(f"Processed {len(processed_entries)} entries.")
    return processed_entries

