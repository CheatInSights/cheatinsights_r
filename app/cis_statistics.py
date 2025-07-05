import re
from collections import defaultdict
from datetime import datetime

# Control terminal output - set to True for detailed debug output, False for checkpoint only
DEBUG_OUTPUT = False


class DOCXStatistics:
    """
    Performs statistical analysis on document data extracted
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


    def debug_print(self, message):
        """
        Print debug messages only if DEBUG_OUTPUT is True.
        
        Args:
            message: The message to print
        """
        if DEBUG_OUTPUT:
            print(message)

    def get_average_num_char_per_unique_rsid(self):
        """
        Calculates the average number of characters per unique RSID actually used in the document's runs.
        """
        used_rsids = set()
        total_char = 0
        for paragraph in self.paragraphs:
            for run in paragraph.get('runs', []):
                rsid = run.get('rsid')
                if rsid:
                    used_rsids.add(rsid)
                    total_char += len(run.get('text', ''))

        if not used_rsids:
            return 0

        return total_char / len(used_rsids)

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

    def _calculate_iqr_outliers(self, data):
        """
        Calculates outliers in a list of data using the IQR method.
        Returns the upper bound threshold and a list of the outlier values.
        """
        if not data:
            return 0, []

        # Sort the data to find quartiles
        sorted_data = sorted(data)
        
        # Calculate Q1 and Q3
        q1_index = int(len(sorted_data) * 0.25)
        q3_index = int(len(sorted_data) * 0.75)
        q1 = sorted_data[q1_index]
        q3 = sorted_data[q3_index]
        
        # Calculate IQR
        iqr = q3 - q1
        
        # Define the upper bound for outliers
        upper_bound = q3 + (1.5 * iqr)
        
        # Find outliers
        outliers = [d for d in data if d > upper_bound]
        
        return upper_bound, outliers

    def calculate_suspicion_score(self):
        self.debug_print("\n\n\n\n DEBUG: HERE calculates suspicion score")
        """
        Calculates a suspicion score based on a set of rules.
        """
        # Rule weights
        SUSPICION_RULES = {
            "different_author": 15,
            "modified_before_created": 25,
            "missing_metadata": 15,
            "long_run_outlier": 25, # high word count per run
            "writing_speed": 20, # New rule for suspicious writing speed
            "rsid_density": 20, # New rule for suspicious RSID density
        }

        # Initialize variables
        score = 0
        factors = []

        # Get metadata using helper methods
        author = self.get_author()
        last_modified_by = self.get_last_modified_by()
        created_time = self.get_created()
        revision = self.get_revision()

        # --- Rule 1: Different Author and Modifier ---
        # (Per-document) Adds 15 if author and last modified by are different
        if author and last_modified_by and author != last_modified_by:
            score += SUSPICION_RULES["different_author"]
            factors.append("Author and Last Modified By are different.")

        # --- Rule 2: Modified Before Created ---
        # (Per-document) Adds 25 if last modified is earlier than created
        if last_modified_by and created_time and created_time > self.metadata.get('docx_core_properties', {}).get('modified', created_time):
            score += SUSPICION_RULES["modified_before_created"]
            factors.append("Document was last modified before it was created.")

        # --- Rule 3: Missing Metadata ---
        # (Per-document) Adds 15 if author, last modified by, or revision is missing
        missing_fields = []
        if not author:
            missing_fields.append("Author")
        if not last_modified_by:
            missing_fields.append("Last Modified By")
        if not revision:
            missing_fields.append("Revision")
        
        if missing_fields:
            score += SUSPICION_RULES["missing_metadata"]
            factors.append(f"Missing key metadata: {', '.join(missing_fields)}.")

        # --- Rule 4: Long Run Outlier Detection (IQR) ---
        # (Per-document) Adds 25 if unusually long text runs are detected
        run_char_counts = self.get_list_char_per_run()
        threshold, long_runs = self._calculate_iqr_outliers(run_char_counts)
        if long_runs:
            score += SUSPICION_RULES["long_run_outlier"]
            factors.append(
                f"{len(long_runs)} unusually long text run(s) detected "
                f"(over {threshold:.0f} chars), suggesting copy-paste."
            )

        # --- Rule 5: Suspicious Writing Speed ---
        # (Per-document) Adds 20 if writing speed is suspiciously high (>200 WPM)
        modified_time = self.metadata.get('docx_core_properties', {}).get('modified')
        if created_time and modified_time and self.word_count > 0:
            try:
                if isinstance(created_time, str):
                    created_time = datetime.strptime(created_time.split('.')[0], '%Y-%m-%dT%H:%M:%S')
                if isinstance(modified_time, str):
                    modified_time = datetime.strptime(modified_time.split('.')[0], '%Y-%m-%dT%H:%M:%S')
                time_diff = modified_time - created_time
                time_diff_minutes = time_diff.total_seconds() / 60
                if time_diff_minutes > 1:
                    words_per_minute = self.word_count / time_diff_minutes
                    if words_per_minute > 200:
                        score += SUSPICION_RULES["writing_speed"]
                        factors.append(
                            f"Suspicious writing speed: {words_per_minute:.0f} words per minute "
                            f"({self.word_count} words in {time_diff_minutes:.1f} minutes)."
                        )
            except (ValueError, TypeError) as e:
                self.debug_print(f"Could not parse dates for writing speed calculation: {e}")

        # --- Rule 6: Suspicious RSID Density (Fixed Threshold) ---
        # (Per-document) Adds 20 if words per unique RSID > 500
        unique_rsid_count = len(self.char_per_unique_rsid)
        if unique_rsid_count > 0 and self.word_count > 0:
            words_per_rsid = self.word_count / unique_rsid_count
            if words_per_rsid > 500:
                score += SUSPICION_RULES["rsid_density"]
                factors.append(
                    f"Suspicious RSID density: {words_per_rsid:.0f} words per unique RSID "
                    f"({self.word_count} words, {unique_rsid_count} unique RSIDs). "
                    f"This suggests copy-pasting or single-session creation."
                )

        # Normalize score (0-100 scale)
        max_possible_score = sum(SUSPICION_RULES.values())
        normalized_score = (score / max_possible_score) * 100 if max_possible_score > 0 else 0

        # Calculate atomic statistics components
        total_characters = sum(self.char_per_unique_rsid)
        total_runs = len(self.char_per_run)
        total_run_characters = sum(self.char_per_run)
        unique_rsid_count = len(self.char_per_unique_rsid)
        
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

    def get_author(self):
        """
        Returns the author/creator of the document from metadata.
        """
        docx_core_props = self.metadata.get('docx_core_properties', {})
        core_props = self.metadata.get('core_properties', {})
        return docx_core_props.get('author') or core_props.get('creator')

    def get_last_modified_by(self):
        """
        Returns the last_modified_by of the document from metadata.
        """
        docx_core_props = self.metadata.get('docx_core_properties', {})
        core_props = self.metadata.get('core_properties', {})
        return docx_core_props.get('last_modified_by') or core_props.get('lastModifiedBy')

    def get_created(self):
        """
        Returns the creation time of the document from metadata.
        """
        docx_core_props = self.metadata.get('docx_core_properties', {})
        core_props = self.metadata.get('core_properties', {})
        return docx_core_props.get('created') or core_props.get('created')

    def get_revision(self):
        """
        Returns the revision number of the document from metadata.
        """
        docx_core_props = self.metadata.get('docx_core_properties', {})
        core_props = self.metadata.get('core_properties', {})
        return docx_core_props.get('revision') or core_props.get('revision')

    def get_metadata_summary(self):
        """
        Returns a summary dictionary of key metadata fields.
        """
        return {
            'author': self.get_author(),
            'last_modified_by': self.get_last_modified_by(),
            'created': self.get_created(),
            'revision': self.get_revision(),
        }