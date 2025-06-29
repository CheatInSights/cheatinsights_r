import json
import os
from bs4 import BeautifulSoup
import colorsys
import hashlib
import io

# Control terminal output - set to True for detailed debug output, False for checkpoint only
DEBUG_OUTPUT = False

class DocumentReconstructor:
    def __init__(self, json_file, document_name=None):
        """
        Initialize the document reconstructor with a JSON file or string.
        
        Args:
            json_file: Either a file path (str) or a file-like object (StringIO) containing JSON data
            document_name: Optional name of the document for unique RSID handling
        """
        self.json_file = json_file
        self.document_name = document_name
        if isinstance(json_file, str):
            with open(json_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
                # print("HERE VVVVV\n")
                # print(self.data)
        else:
            # Handle file-like object
            self.data = json.load(json_file)
        self.rsid_colors = self._generate_rsid_colors()

    def debug_print(self, message):
        """
        Print debug messages only if DEBUG_OUTPUT is True.
        
        Args:
            message: The message to print
        """
        if DEBUG_OUTPUT:
            print(message)

    def _generate_rsid_colors(self):
        """
        Generate a unique color for each RSID in the document.
        Uses a hash function to ensure consistent colors for the same RSID.
        If document_name is provided, it's included in the hash to ensure
        different colors for the same RSID across different documents.
        
        Returns:
            dict: Mapping of RSIDs to hex color codes
        """
        rsid_colors = {}
        unique_rsids = set()
        
        # Collect all unique RSIDs
        for para in self.data:
            for run in para["runs"]:
                if run["rsid"]:
                    unique_rsids.add(run["rsid"])
        
        # Generate colors for each RSID
        for rsid in unique_rsids:
            # Use hash of RSID (and document name if provided) to generate consistent color
            hash_input = rsid
            if self.document_name:
                hash_input = f"{self.document_name}_{rsid}"
            
            hash_object = hashlib.md5(hash_input.encode())
            hash_value = int(hash_object.hexdigest(), 16)
            
            # Convert hash to HSV color space for better color distribution
            hue = (hash_value % 360) / 360.0
            saturation = 0.3  # Lower saturation for pastel colors
            value = 0.95     # High value for light background
            
            # Convert HSV to RGB
            rgb = colorsys.hsv_to_rgb(hue, saturation, value)
            
            # Convert RGB to hex
            hex_color = '#{:02x}{:02x}{:02x}'.format(
                int(rgb[0] * 255),
                int(rgb[1] * 255),
                int(rgb[2] * 255)
            )
            
            rsid_colors[rsid] = hex_color
        
        return rsid_colors

    def create_html(self, output_file=None):
        """
        Create an HTML file from the JSON data.
        
        Args:
            output_file (str, optional): Path to the output HTML file. If not provided,
                                       returns HTML string.
        
        Returns:
            str: Either path to the created HTML file or HTML string
        """
        # Generate CSS rules for RSID colors
        rsid_css = ""
        for rsid, color in self.rsid_colors.items():
            rsid_css += f"""
            .run[data-rsid="{rsid}"] {{
                background-color: {color};
                border-radius: 2px;
                padding: 0 2px;
            }}"""

        # Create HTML structure
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reconstructed Document</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.4;
            margin: 0 auto;
            padding: 20px;
        }}
        .paragraph {{
            margin-bottom: 0.5em;  /* Reduced from 1em to 0.5em */
            position: relative;
            min-height: 1.2em;    /* Reduced from 1.5em to 1.2em */
        }}
        .run {{
            display: inline;
        }}
        .paragraph-id {{
            position: absolute;
            left: -150px;
            color: #999;
            font-size: 0.8em;
        }}
        .rsid {{
            color: #666;
            font-size: 0.8em;
            margin-left: 5px;
        }}
        .empty-paragraph {{
            border-left: 2px solid #ddd;
            padding-left: 10px;
            margin-left: 5px;
            margin-bottom: 0.3em;  /* Even smaller margin for empty paragraphs */
        }}
        .empty-paragraph::before {{
            content: "¶";  /* Paragraph symbol */
            color: #999;
            font-size: 0.8em;
            margin-right: 5px;
        }}
        {rsid_css}
        /* Add more styling as needed */
    </style>
</head>
<body>
"""

        # Process each paragraph
        for para in self.data:
            # Start paragraph
            is_empty = len(para["runs"]) == 0
            empty_class = ' class="empty-paragraph"' if is_empty else ''
            html_content += f'<div class="paragraph"{empty_class} data-para-id="{para["id"]}">\n'
            
            # Add paragraph ID as a hidden element
            html_content += f'    <span class="paragraph-id">{para["id"]}</span>\n'
            
            # Process each run in the paragraph
            for run in para["runs"]:
                # Create a span for each run with its RSID
                html_content += f'    <span class="run" data-rsid="{run["rsid"]}">{run["text"]}</span>\n'
            
            # End paragraph
            html_content += '</div>\n'

        # Close HTML structure
        html_content += """</body>
</html>"""

        if output_file is None:
            return html_content

        # Write to file if output_file is provided
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        self.debug_print(f"DEBUG Created HTML file: {output_file}")
        self.debug_print("output_file \n")

        return output_file

def main():
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python json_to_html.py <path_to_json_file>")
        sys.exit(1)

    json_file = sys.argv[1]
    if not os.path.exists(json_file):
        print(f"Error: JSON file {json_file} does not exist")
        sys.exit(1)

    reconstructor = DocumentReconstructor(json_file)
    output_file = reconstructor.create_html()
    print(f"Successfully created HTML file: {output_file}")

if __name__ == "__main__":
    main() 