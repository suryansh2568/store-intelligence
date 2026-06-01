#!/usr/bin/env python3
"""Fix session_seq in events file."""
import json

input_file = "data/events_from_video.jsonl"
output_file = "data/events.jsonl"

with open(input_file, 'r') as f_in, open(output_file, 'w') as f_out:
    for line in f_in:
        event = json.loads(line)
        # Fix session_seq: change 0 to 1
        if event['metadata']['session_seq'] == 0:
            event['metadata']['session_seq'] = 1
        f_out.write(json.dumps(event) + '\n')

print(f"Fixed events written to {output_file}")
