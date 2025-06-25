import zipfile
from bs4 import BeautifulSoup
import json
import os
import io
from datetime import datetime
from docx import Document  # You would need to: pip install python-docx


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
        Initializes the Extract class by extracting all available metadata XML files.
        
        Args:
            file: Either a file path (str) or a file-like object (BytesIO) containing the .docx file
        """
        self.sourcefile = file
        with zipfile.ZipFile(file) as zip:
            # Document content
            self.document_content = zip.read('word/document.xml')
            
            # Settings content
            try:
                self.settings_content = zip.read('word/settings.xml')
            except KeyError:
                self.settings_content = None
                print("[DEBUG] No settings.xml found in the .docx file.")
            
            # App properties
            try:
                self.app_content = zip.read('docProps/app.xml')
            except KeyError:
                self.app_content = None
                print("[DEBUG] No app.xml found in the .docx file.")
                
            # Core properties
            try:
                self.core_content = zip.read('docProps/core.xml')
            except KeyError:
                self.core_content = None
                print("[DEBUG] No core.xml found in the .docx file.")
                
            # Custom properties
            try:
                self.custom_content = zip.read('docProps/custom.xml')
            except KeyError:
                self.custom_content = None
                print("[DEBUG] No custom.xml found in the .docx file.")

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

    def get_settings_rsids(self):
        """
        Parse settings.xml and return all unique RSID values and their sources as structured data.
        
        Returns:
            dict: A dictionary containing:
                - rsids: List of dictionaries with RSID values and their sources
                - total_count: Total number of unique RSIDs
                Example:
                {
                    'rsids': [
                        {
                            'value': '001234AB',
                            'sources': ['w:rsidRoot', 'w:rsidR']
                        },
                        ...
                    ],
                    'total_count': 10
                }
        """
        if not self.settings_content:
            return {'rsids': [], 'total_count': 0}
        
        soup = BeautifulSoup(self.settings_content, 'xml')
        
        # Find all elements that contain 'rsid' in their tag name
        rsid_elements = soup.find_all(lambda tag: 'rsid' in tag.name.lower())
        
        # Use a dictionary to track which tags use each RSID
        rsid_sources = {}
        
        for rsid in rsid_elements:
            rsid_value = rsid.get('w:val')
            if rsid_value:
                if rsid_value not in rsid_sources:
                    rsid_sources[rsid_value] = set()
                rsid_sources[rsid_value].add(rsid.name)
        
        # Convert to sorted list of dictionaries for JSON serialization
        rsids_list = [
            {
                'value': rsid_value,
                'sources': sorted(list(sources))
            }
            for rsid_value, sources in rsid_sources.items()
        ]
        
        # Sort by RSID value
        rsids_list.sort(key=lambda x: x['value'])
        
        return {
            'rsids': rsids_list,
            'total_count': len(rsids_list)
        }


    # THIS FUNCTION IS FOR DEBUGGING
    def print_settings_rsids(self):
        """
        Parse settings.xml and print all unique RSID values found in the file, including rsidRoot and other RSID-related elements.
        """
        rsid_data = self.get_settings_rsids()
        
        if rsid_data['total_count'] == 0:
            print("[DEBUG] No settings.xml found in the .docx file or no RSIDs found.")
            return
        
        print(f"Found {rsid_data['total_count']} unique RSID values:")
        for rsid_info in rsid_data['rsids']:
            print(f"RSID: {rsid_info['value']} (found in: {', '.join(rsid_info['sources'])})")



# METADATA EXTRACTION AND PARSING

    def get_app_properties(self):
        """
        Extract application properties from app.xml and return as a dictionary.
        """
        if not self.app_content:
            return {}
        
        soup = BeautifulSoup(self.app_content, 'xml')
        app_props = {}
        for element in soup.find_all():
            if element.string and element.string.strip():
                app_props[element.name] = element.string.strip()
        return app_props

    def get_core_properties(self):
        """
        Extract core document properties from core.xml
        """
        if not self.core_content:
            return {}
            
        soup = BeautifulSoup(self.core_content, 'xml')
        core_props = {}
        
        # Common core properties
        properties = [
            'title', 'subject', 'creator', 'keywords', 'description',
            'lastModifiedBy', 'revision', 'created', 'modified'
        ]
        
        for prop in properties:
            elem = soup.find(prop)
            if elem and elem.string:
                # Convert dates to datetime objects
                if prop in ['created', 'modified']:
                    try:
                        core_props[prop] = datetime.strptime(elem.string.split('.')[0], '%Y-%m-%dT%H:%M:%S')
                    except ValueError:
                        core_props[prop] = elem.string
                else:
                    core_props[prop] = elem.string.strip()
                    
        return core_props

    def get_metadata(self):
        """
        Collect all available metadata from the document using both direct XML parsing
        and python-docx (if available)
        """
        metadata = {
            'core_properties': self.get_core_properties(),
            'app_properties': self.get_app_properties(),
            'custom_properties': {},
        }
        
        # Try to get additional metadata using python-docx
        try:
            doc = Document(self.sourcefile)
            
            # Core properties through python-docx
            core_props = doc.core_properties
            metadata['docx_core_properties'] = {
                'author': core_props.author,
                'category': core_props.category,
                'comments': core_props.comments,
                'content_status': core_props.content_status,
                'created': core_props.created,
                'identifier': core_props.identifier,
                'keywords': core_props.keywords,
                'language': core_props.language,
                'last_modified_by': core_props.last_modified_by,
                'last_printed': core_props.last_printed,
                'modified': core_props.modified,
                'revision': core_props.revision,
                'subject': core_props.subject,
                'title': core_props.title,
                'version': core_props.version
            }
            
            # Custom properties
            metadata['docx_custom_properties'] = {}
            for prop in doc.custom_properties:
                metadata['docx_custom_properties'][prop.name] = prop.value
                
        except Exception as e:
            print(f"[DEBUG] Could not extract python-docx metadata: {str(e)}")
            
        return metadata

    # def get_rsids(self):
    #     """
    #     Get unique RSIDs with their sources
    #     """
    #     if not self.settings_content:
    #         return {}
            
    #     soup = BeautifulSoup(self.settings_content, 'xml')
    #     rsid_elements = soup.find_all(lambda tag: 'rsid' in tag.name.lower())
        
    #     rsids = {}
    #     for rsid in rsid_elements:
    #         rsid_value = rsid.get('w:val')
    #         if rsid_value:
    #             if rsid_value not in rsids:
    #                 rsids[rsid_value] = []
    #             rsids[rsid_value].append(rsid.name)
                
    #     return rsids


def main():
    import sys
    if len(sys.argv) != 2:
        print("Usage: python cis_extractor.py <path_to_docx_file>")
        sys.exit(1)
    docx_path = sys.argv[1]
    extractor = Extract(docx_path)
    
    # Print RSIDs to terminal
    extractor.print_settings_rsids()
    
    print("\n========== METADATA SECTION ==========")
    # Get all metadata
    metadata = extractor.get_all_metadata()
    print("\n========== METADATA FROM core.xml ==========")
    print(json.dumps(metadata.get('core_properties', {}), indent=2, default=str))
    
    print("\n========== METADATA FROM app.xml ==========")
    print(json.dumps(metadata.get('app_properties', {}), indent=2, default=str))
    
    print("\n========== METADATA FROM custom.xml ==========")
    print(json.dumps(metadata.get('custom_properties', {}), indent=2, default=str))
    
    # print("\n========== RSIDs FROM settings.xml ==========")
    # print(json.dumps(metadata.get('rsids', {}), indent=2, default=str))
    
    print("\n========== METADATA FROM python-docx (core properties) ==========")
    print(json.dumps(metadata.get('docx_core_properties', {}), indent=2, default=str))
    
    print("\n========== METADATA FROM python-docx (custom properties) ==========")
    print(json.dumps(metadata.get('docx_custom_properties', {}), indent=2, default=str))

    
    # Also demonstrate JSON output
    # import json
    # rsid_data = extractor.get_settings_rsids()
    # print("\nJSON representation:")
    # print(json.dumps(rsid_data, indent=2))

if __name__ == "__main__":
    main()