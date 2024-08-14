import os
import base64
import re
from anthropic import Anthropic
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import random
import _api 

anthropic = Anthropic(api_key=_api.API_KEY)

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

class DentalChatBot:
    def __init__(self):
        self.conversation_history = []

    def analyze_dental_xray(self, image_path):
        base64_image = encode_image(image_path)

        initial_prompt = {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64_image
                    }
                },
                {
                    "type": "text",
                    "text": """This is a panoramic dental X-ray. Please analyze it as a dentist would, identifying any visible issues or abnormalities. Focus on tooth decay, gum disease, bone loss, impacted teeth, and any other notable findings.

Please provide your analysis in SOAP format:

Subjective: Briefly describe the patient's presenting complaint or reason for the X-ray (if apparent from the image).

Objective: List your observations from the X-ray. For each finding, provide:
1. A brief description of the issue
2. The approximate location using a coordinate system where (0,0) is the top-left corner and (1000,1000) is the bottom-right corner of the image.

Format each finding as follows:
FINDING: [Brief description]
LOCATION: [x1,y1,x2,y2]

Where (x1,y1) is the top-left corner and (x2,y2) is the bottom-right corner of a bounding box around the area of interest.

Assessment: Provide an overall assessment of the patient's dental health based on the X-ray findings.

Plan: Suggest a treatment plan or further actions based on the findings."""
                }
            ]
        }

        self.conversation_history.append(initial_prompt)

        response = self._get_claude_response()
        parsed_response = self._parse_soap_response(response)

        # Annotate the image and get numbered findings
        annotated_image, numbered_findings = annotate_image(image_path, parsed_response['findings'])

        # Save the annotated image
        annotated_filename = f"annotated_{os.path.basename(image_path)}"
        annotated_filepath = os.path.join(os.path.dirname(image_path), annotated_filename)
        annotated_image.save(annotated_filepath)

        # Update the parsed response with numbered findings
        parsed_response['findings'] = numbered_findings
        parsed_response['annotated_image_path'] = annotated_filepath

        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })

        return parsed_response

    def continue_conversation(self, user_input):
        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })

        response = self._get_claude_response()

        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })

        return response

    def _get_claude_response(self):
        response = anthropic.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1000,
            messages=self.conversation_history
        )
        return response.content[0].text

    def _parse_soap_response(self, text):
        soap_sections = {}
        current_section = None
        findings = []

        for line in text.split('\n'):
            if line.strip().lower() in ['subjective:', 'objective:', 'assessment:', 'plan:']:
                current_section = line.strip().lower()[:-1]
                soap_sections[current_section] = []
            elif current_section:
                soap_sections[current_section].append(line.strip())

        if 'objective' in soap_sections:
            pattern = r'FINDING: (.*?)\nLOCATION: \[(\d+),(\d+),(\d+),(\d+)\]'
            matches = re.findall(pattern, '\n'.join(soap_sections['objective']), re.DOTALL)
            
            for match in matches:
                description = match[0].strip()
                coordinates = [int(match[1]), int(match[2]), int(match[3]), int(match[4])]
                findings.append({
                    'description': description,
                    'coordinates': coordinates
                })

        return {
            'soap': soap_sections,
            'findings': findings
        }

def annotate_image(image_path, findings):
    image = Image.open(image_path)
    
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.5)
    
    enhancer = ImageEnhance.Brightness(image)
    image = enhancer.enhance(1.2)
    
    draw = ImageDraw.Draw(image)
    
    colors = [
        '#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', 
        '#00FFFF', '#FF8000', '#8000FF', '#0080FF', '#FF0080'
    ]
    
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font = ImageFont.load_default()

    numbered_findings = []
    for i, finding in enumerate(findings, 1):
        x1, y1, x2, y2 = finding['coordinates']
        x1 = int(x1 * image.width / 1000)
        y1 = int(y1 * image.height / 1000)
        x2 = int(x2 * image.width / 1000)
        y2 = int(y2 * image.height / 1000)
        
        color = random.choice(colors)
        
        overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle([x1, y1, x2, y2], fill=color + '40')
        image = Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB')
        
        draw = ImageDraw.Draw(image)
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        
        label = str(i)
        left, top, right, bottom = draw.textbbox((x1, y1), label, font=font)
        label_w, label_h = right - left, bottom - top
        draw.rectangle([x1, y1, x1 + label_w + 4, y1 + label_h + 4], fill=color)
        draw.text((x1 + 2, y1 + 2), label, fill='white', font=font)
        
        numbered_findings.append({
            'number': i,
            'description': finding['description'],
            'coordinates': finding['coordinates'],
            'color': color
        })

    return image, numbered_findings