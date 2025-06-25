import zipfile
from bs4 import BeautifulSoup
import json
import os
import io


class Extract:
    """
    Handles the extraction of content and RSIDs from a .docx file.
    RSIDs (Revision Session IDs) are unique identifiers that track changes in Word documents.
    """
    # XML tag constants for parsing the document structure
    BODY_TAG = "w:body"  # Main document body tag
    PARAGRAPH_TAG = "p"  # Paragraph tag
    RUN_TAG = "r"  # Text run tag (a continuous segment of text with the same formatting)
    TEXT_TAG = "t"  # Actual text content tag
    RSIDR_PROPERTY = "w:rsidR"  # RSID property for runs
    PARAGRAPH_ID_PROPERTY = "w14:paraId"  # Unique paragraph identifier
    HYPERLINK_TAG = "hyperlink"  # Hyperlink tag

    def __init__(self, file):
        """
        Initializes the Extract class by extracting document XML content.
        
        Args:
            file: Either a file path (str) or a file-like object (BytesIO) containing the .docx file
        """
        self.sourcefile = file
        if isinstance(file, (str, bytes)):
            with zipfile.ZipFile(file) as zip:
                self.document_content = zip.read('word/document.xml')
        else:
            # Handle file-like object
            with zipfile.ZipFile(file) as zip:
                self.document_content = zip.read('word/document.xml')

    def get_paragraphs(self):
        """
        Get all paragraphs from the document with their runs and RSIDs.
        Now includes empty paragraphs and assigns placeholder IDs when none exist.
        
        Returns:
            list: A list of dictionaries containing paragraph information:
                - id: Unique paragraph identifier (or placeholder if none exists)
                - rsid: Revision Session ID for the paragraph
                - runs: List of text runs with their RSIDs
                - xml: Original XML string of the paragraph
        """
        paragraphs = []
        soup = BeautifulSoup(self.document_content, 'xml')
        body = soup.find(self.BODY_TAG)
        
        if body is None:
            print("[DEBUG] No body tag found in document")
            return paragraphs
            
        print(f"\n[DEBUG] Processing document body with {len(list(body.children))} children")
        
        for i, child in enumerate(body.children):
            if not hasattr(child, 'name') or child.name != self.PARAGRAPH_TAG:
                continue
                
            print(f"\n[DEBUG] Processing paragraph {i}")
            
            # Get paragraph ID or create a placeholder
            paragraph_id = child.get(self.PARAGRAPH_ID_PROPERTY)
            if paragraph_id is None:
                paragraph_id = f"placeholder_{i}"
                print(f"[DEBUG] No ID found for paragraph {i}, using placeholder: {paragraph_id}")
            
            paragraph_info = {
                'id': paragraph_id,
                'rsid': child.get(self.RSIDR_PROPERTY, None),
                'runs': [],
                'xml': str(child)
            }
            
            print(f"[DEBUG] Paragraph ID: {paragraph_info['id']}, RSID: {paragraph_info['rsid']}")
            
            # Process all runs, including those in hyperlinks
            all_runs = child.find_all(self.RUN_TAG, recursive=True)
            print(f"[DEBUG] Found {len(all_runs)} runs in paragraph")
            
            for j, run in enumerate(all_runs):
                text_tag = run.find(self.TEXT_TAG)
                if text_tag is None:
                    print(f"[DEBUG] Run {j}: No text tag found")
                    continue
                    
                text = text_tag.string or ''
                run_rsid = run.get(self.RSIDR_PROPERTY, paragraph_info['rsid'])
                print(f"[DEBUG] Run {j}: Text='{text}', RSID={run_rsid}")
                
                paragraph_info['runs'].append({
                    'text': text,
                    'rsid': run_rsid
                })
            
            # Always add the paragraph, even if it has no runs
            print(f"[DEBUG] Adding paragraph with {len(paragraph_info['runs'])} runs")
            paragraphs.append(paragraph_info)
            
        print(f"\n[DEBUG] Total paragraphs extracted: {len(paragraphs)}")
        return paragraphs

    def save_to_json(self, output_file=None):
        """
        Save the extracted paragraphs to a JSON file or return as string.
        
        Args:
            output_file (str, optional): Path to the output JSON file. If not provided,
                                       returns JSON string.
        
        Returns:
            str: Either path to the created JSON file or JSON string
        """
        paragraphs = self.get_paragraphs()
        
        if output_file is None:
            return json.dumps(paragraphs, indent=2, ensure_ascii=False)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(paragraphs, f, indent=2, ensure_ascii=False)
        
        print(f"[DEBUG] Saved results to {output_file}")
        return output_file