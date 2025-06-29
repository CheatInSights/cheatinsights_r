import zipfile
from bs4 import BeautifulSoup
import json
import os
import io
from datetime import datetime
from docx import Document  # You would need to: pip install python-docx

# Control terminal output - set to True for detailed debug output, False for checkpoint only
DEBUG_OUTPUT = False

# Control found message output - set to True to show found messages, False to hide them
FOUND_OUTPUT = False


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
    INSRSID_PROPERTY = "w:insrsid"  # RSID property for insertions
    RSIDRDEFAULT_PROPERTY = "w:rsidRDefault"  # Default RSID property for paragraphs
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
                self.debug_print("[DEBUG] No settings.xml found in the .docx file.")
            
            # App properties
            try:
                self.app_content = zip.read('docProps/app.xml')
            except KeyError:
                self.app_content = None
                self.debug_print("[DEBUG] No app.xml found in the .docx file.")
                
            # Core properties
            try:
                self.core_content = zip.read('docProps/core.xml')
            except KeyError:
                self.core_content = None
                self.debug_print("[DEBUG] No core.xml found in the .docx file.")
                
            # Custom properties
            try:
                self.custom_content = zip.read('docProps/custom.xml')
            except KeyError:
                self.custom_content = None
                self.debug_print("[DEBUG] No custom.xml found in the .docx file.")

    def debug_print(self, message):
        """
        Print debug messages only if DEBUG_OUTPUT is True.
        
        Args:
            message: The message to print
        """
        if DEBUG_OUTPUT:
            print(message)

    def found_print(self, message):
        """
        Print found messages only if FOUND_OUTPUT is True.
        
        Args:
            message: The message to print
        """
        if FOUND_OUTPUT:
            print(message)
            
    def get_paragraphs(self):
        """
        Get all paragraphs from the document with their runs and RSIDs.
        Now includes empty paragraphs and assigns placeholder IDs when none exist.
        
        Returns:
            list: A list of dictionaries containing paragraph information:
                - id: Unique paragraph identifier (or placeholder if none exists)
                - rsid: Revision Session ID for the paragraph
                - rsid_default: Default RSID for the paragraph
                - runs: List of text runs with their RSIDs
                - xml: Original XML string of the paragraph
        """
        paragraphs = []
        soup = BeautifulSoup(self.document_content, 'xml')
        body = soup.find(self.BODY_TAG)
        
        if body is None:
            self.debug_print("[DEBUG] No body tag found in document")
            return paragraphs
            
        self.debug_print(f"\n[DEBUG] Processing document body with {len(list(body.children))} children")
        
        for i, child in enumerate(body.children):
            if not hasattr(child, 'name') or child.name != self.PARAGRAPH_TAG:
                continue
                
            self.debug_print(f"\n[DEBUG] Processing paragraph {i}")
            
            # Get paragraph ID or create a placeholder
            paragraph_id = child.get(self.PARAGRAPH_ID_PROPERTY)
            if paragraph_id is None:
                paragraph_id = f"placeholder_{i}"
                self.debug_print(f"[DEBUG] No ID found for paragraph {i}, using placeholder: {paragraph_id}")
            
            # Check for rsidRDefault in paragraph
            paragraph_rsid_default = child.get(self.RSIDRDEFAULT_PROPERTY)
            if paragraph_rsid_default:
                self.found_print(f"[FOUND] Paragraph {i} has rsidRDefault: {paragraph_rsid_default}")
            
            paragraph_info = {
                'id': paragraph_id,
                'rsid': child.get(self.RSIDR_PROPERTY, None),
                'rsid_default': paragraph_rsid_default,
                'runs': [],
                'xml': str(child)
            }
            
            self.debug_print(f"[DEBUG] Paragraph ID: {paragraph_info['id']}, RSID: {paragraph_info['rsid']}")
            
            # Process all runs, including those in hyperlinks
            all_runs = child.find_all(self.RUN_TAG, recursive=True)
            self.debug_print(f"[DEBUG] Found {len(all_runs)} runs in paragraph")
            
            for j, run in enumerate(all_runs):
                text_tag = run.find(self.TEXT_TAG)
                if text_tag is None:
                    self.debug_print(f"[DEBUG] Run {j}: No text tag found")
                    continue
                    
                text = text_tag.string or ''
                run_rsid = run.get(self.RSIDR_PROPERTY, paragraph_info['rsid'])
                
                # Check for insrsid in run
                run_insrsid = run.get(self.INSRSID_PROPERTY)
                if run_insrsid:
                    self.found_print(f"[FOUND] Run {j} in paragraph {i} has insrsid: {run_insrsid} (text: '{text}')")
                
                self.debug_print(f"[DEBUG] Run {j}: Text='{text}', RSID={run_rsid}")
                
                paragraph_info['runs'].append({
                    'text': text,
                    'rsid': run_rsid,
                    'insrsid': run_insrsid
                })
            
            # Always add the paragraph, even if it has no runs
            self.debug_print(f"[DEBUG] Adding paragraph with {len(paragraph_info['runs'])} runs")
            paragraphs.append(paragraph_info)
            
        self.debug_print(f"\n[DEBUG] Total paragraphs extracted: {len(paragraphs)}")
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
        
        self.debug_print(f"[DEBUG] Saved results to {output_file}")
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
            self.debug_print("[DEBUG] No settings.xml found in the .docx file or no RSIDs found.")
            return
        
        self.found_print(f"Found {rsid_data['total_count']} unique RSID values:")
        for rsid_info in rsid_data['rsids']:
            self.found_print(f"RSID: {rsid_info['value']} (found in: {', '.join(rsid_info['sources'])})")



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
            self.debug_print(f"[DEBUG] Could not extract python-docx metadata: {str(e)}")
            
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

    # def check_advanced_rsids(self):
    #     """
    #     Check for advanced RSID types (insrsid, rsidRDefault) in the document and output findings to terminal.
    #     """
    #     print("\n" + "="*60)
    #     print("CHECKING FOR ADVANCED RSID TYPES")
    #     print("="*60)
        
    #     # Check settings.xml for advanced RSID types
    #     if self.settings_content:
    #         soup = BeautifulSoup(self.settings_content, 'xml')
            
    #         # Check for insrsid elements
    #         insrsid_elements = soup.find_all(lambda tag: 'insrsid' in tag.name.lower())
    #         if insrsid_elements:
    #             self.found_print(f"[FOUND] {len(insrsid_elements)} insrsid elements in settings.xml:")
    #             for elem in insrsid_elements:
    #                 rsid_value = elem.get('w:val')
    #                 self.found_print(f"  - {elem.name}: {rsid_value}")
    #         else:
    #             print("[NOT FOUND] No insrsid elements in settings.xml")
            
    #         # Check for rsidRDefault elements
    #         rsidrdefault_elements = soup.find_all(lambda tag: 'rsidrdefault' in tag.name.lower())
    #         if rsidrdefault_elements:
    #             self.found_print(f"[FOUND] {len(rsidrdefault_elements)} rsidRDefault elements in settings.xml:")
    #             for elem in rsidrdefault_elements:
    #                 rsid_value = elem.get('w:val')
    #                 self.found_print(f"  - {elem.name}: {rsid_value}")
    #         else:
    #             print("[NOT FOUND] No rsidRDefault elements in settings.xml")
    #     else:
    #         print("[NOT FOUND] No settings.xml available to check")
        
    #     print("="*60)
    #     print("END OF ADVANCED RSID CHECK")
    #     print("="*60 + "\n")


def main():
    import sys
    if len(sys.argv) != 2:
        print("Usage: python cis_extractor.py <path_to_docx_file>")
        sys.exit(1)
    docx_path = sys.argv[1]
    extractor = Extract(docx_path)
    
    # Check for advanced RSID types
    # extractor.check_advanced_rsids()
    
    # Print RSIDs to terminal
    extractor.print_settings_rsids()
    
    # Always print checkpoint message
    print("[CHECKPOINT] Document processing completed successfully")

if __name__ == "__main__":
    main()