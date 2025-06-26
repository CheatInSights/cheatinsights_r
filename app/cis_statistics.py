import re
from collections import defaultdict


class DOCXStatistics:
    """
    Performs statistical analysis on document data extracted by the Extract class.
    Computes averages and distributions of characters per RSID and per run.
    """

    def __init__(self, paragraphs, metadata, settings_rsids):
        """
        Initializes the DOCXStatistics object with statistical calculations.
        
        Args:
            paragraphs: List of paragraph dictionaries from Extract.get_paragraphs()
            metadata: Dictionary of metadata from Extract.get_metadata()
            settings_rsids: Dictionary of RSID information from Extract.get_settings_rsids()
        """
        self.paragraphs = paragraphs
        self.metadata = metadata
        self.settings_rsids = settings_rsids
        
        # Calculate statistics
        self.average_num_char_per_unique_rsid = self.get_average_num_char_per_unique_rsid()
        self.average_num_char_per_run = self.get_average_num_char_per_run()
        self.char_per_unique_rsid = self.get_list_char_per_unique_rsid()
        self.char_per_run = self.get_list_char_per_run()
        self.word_count = self.get_word_count()
        self.short_paragraph_count = self.get_short_paragraph_count()

    def get_average_num_char_per_unique_rsid(self):
        """
        Calculates the average number of characters per unique RSID.
        """
        # Get unique RSIDs from settings
        unique_rsids = set()
        if self.settings_rsids and 'rsids' in self.settings_rsids:
            unique_rsids = {rsid['value'] for rsid in self.settings_rsids['rsids']}
        
        if not unique_rsids:
            return 0
            
        # Calculate total characters
        total_char = 0
        for paragraph in self.paragraphs:
            for run in paragraph.get('runs', []):
                total_char += len(run.get('text', ''))

        return total_char / len(unique_rsids) if unique_rsids else 0

    def get_average_num_char_per_run(self):
        """
        Calculates the average number of characters per run in the document.
        """
        total_char = 0
        total_runs = 0
        
        for paragraph in self.paragraphs:
            for run in paragraph.get('runs', []):
                total_char += len(run.get('text', ''))
                total_runs += 1

        return total_char / total_runs if total_runs > 0 else 0

    def get_list_char_per_unique_rsid(self):
        """
        Returns a list of character counts per unique RSID.
        """
        rsid_char_count_dict = defaultdict(int)
        
        for paragraph in self.paragraphs:
            for run in paragraph.get('runs', []):
                rsid = run.get('rsid')
                if rsid:
                    rsid_char_count_dict[rsid] += len(run.get('text', ''))
                    
        return list(rsid_char_count_dict.values())

    def get_list_char_per_run(self):
        """
        Returns a list of character counts per run in the document.
        """
        count_char_txt = []
        
        for paragraph in self.paragraphs:
            for run in paragraph.get('runs', []):
                count_char_txt.append(len(run.get('text', '')))
                
        return count_char_txt

    def get_word_count(self):
        """
        Calculates the total number of words in the document.
        """
        total_words = 0
        
        for paragraph in self.paragraphs:
            for run in paragraph.get('runs', []):
                text = run.get('text', '')
                total_words += len(text.split())  # Split by spaces to count words
                
        return total_words

    def get_short_paragraph_count(self, threshold=30):
        """
        Counts the number of paragraphs with fewer than `threshold` characters.
        """
        short_count = 0
        
        for paragraph in self.paragraphs:
            total_chars = 0
            for run in paragraph.get('runs', []):
                total_chars += len(run.get('text', ''))
            if total_chars < threshold:
                short_count += 1
                
        return short_count

    def calculate_suspicion_score(self):
        print("\n\n\n\n HERE calcualtes suspicion score")
        """
        Calculates a suspicion score based on the following rules:
        1. Different Author and Modifier.
        2. Missing Metadata.
        3. High Average Characters Per RSID.
        """
        # Rule weights
        SUSPICION_RULES = {
            "different_author": 20,
            "missing_metadata": 15,
            "high_avg_chars_per_rsid": 25,
        }

        # Initialize variables
        score = 0
        factors = []

        # Get metadata from the nested structure
        docx_core_props = self.metadata.get('docx_core_properties', {})
        core_props = self.metadata.get('core_properties', {})
        
        # Rule 1: Different Author and Modifier
        created_by = docx_core_props.get('author') or core_props.get('creator')
        modified_by = docx_core_props.get('last_modified_by') or core_props.get('lastModifiedBy')
        
        if created_by and modified_by and created_by != modified_by:
            score += SUSPICION_RULES["different_author"]
            factors.append("Created By and Last Modified By are different.")

        # Rule 2: Missing Metadata
        required_metadata = ["author", "last_modified_by", "revision"]
        missing_metadata = [
            field for field in required_metadata 
            if not docx_core_props.get(field) and not core_props.get(field)
        ]
        if missing_metadata:
            score += SUSPICION_RULES["missing_metadata"]
            factors.append(f"Missing Metadata: {', '.join(missing_metadata)}.")

        # Rule 3: High Average Characters Per RSID
        rsid_count = len(self.char_per_unique_rsid)
        total_chars = sum(self.char_per_unique_rsid)
        avg_chars_per_rsid = total_chars / rsid_count if rsid_count > 0 else 0
        if avg_chars_per_rsid > 200:  # Threshold: 200 characters per RSID
            score += SUSPICION_RULES["high_avg_chars_per_rsid"]
            factors.append(
                f"High Average Characters Per RSID: {avg_chars_per_rsid:.2f} (Threshold: 200)"
            )

        # Normalize score (0-100 scale)
        max_possible_score = sum(SUSPICION_RULES.values())
        normalized_score = (score / max_possible_score) * 100

        # Calculate atomic statistics components
        total_characters = sum(self.char_per_unique_rsid)
        total_runs = len(self.char_per_run)
        total_run_characters = sum(self.char_per_run)
        unique_rsid_count = len(self.char_per_unique_rsid)
        
        # Calculate averages for reference (but also provide atomic components)
        avg_chars_per_rsid = total_characters / unique_rsid_count if unique_rsid_count > 0 else 0
        avg_chars_per_run = total_run_characters / total_runs if total_runs > 0 else 0

        return {
            "score": round(normalized_score, 2),
            "total_score": round(score, 2),
            "factors": factors,
            "statistics": {
                # Atomic components
                "total_characters_count": total_characters,
                "total_word_count": self.word_count,
                "total_paragraph_count": len(self.paragraphs),

                "total_runs_count": total_runs,
                "unique_rsid_count": unique_rsid_count,



                # Calculated averages (for reference)
                "average_chars_per_rsid": round(avg_chars_per_rsid, 2),
                "average_chars_per_run": round(avg_chars_per_run, 2),
                "average_words_per_rsid": round(self.word_count / unique_rsid_count, 2) if unique_rsid_count > 0 else 0,
                "average_words_per_run": round(self.word_count / total_runs, 2) if total_runs > 0 else 0,
            }
        }