from django.test import TestCase
from .cis_statistics import DOCXStatistics
from datetime import datetime, timedelta

# Create your tests here.

class DOCXStatisticsPerDocumentRulesTests(TestCase):
    def setUp(self):
        """Set up common base data for tests."""
        self.base_paragraphs = []
        self.base_settings_rsids = {'rsids': [{'value': '001'}, {'value': '002'}]}
        # Mock metadata for a "clean" document
        self.clean_metadata = {
            'docx_core_properties': {
                'author': 'Test Author',
                'last_modified_by': 'Test Author',
                'created': datetime(2023, 1, 1),
                'modified': datetime(2023, 1, 2),
                'revision': '1',
            },
            'core_properties': {}
        }

    def test_clean_document_no_suspicion(self):
        """Test that a clean document has a score of 0."""
        stats = DOCXStatistics(self.base_paragraphs, self.clean_metadata, self.base_settings_rsids)
        result = stats.calculate_suspicion_score()
        self.assertEqual(result['score'], 0)
        self.assertEqual(len(result['factors']), 0)

    def test_different_author_rule(self):
        """Test the 'different author and last_modified_by' rule."""
        metadata = self.clean_metadata.copy()
        metadata['docx_core_properties']['last_modified_by'] = 'Different Person'
        stats = DOCXStatistics(self.base_paragraphs, metadata, self.base_settings_rsids)
        result = stats.calculate_suspicion_score()
        self.assertIn("Author and Last Modified By are different.", result['factors'])
        self.assertGreater(result['score'], 0)

    def test_modified_before_created_rule(self):
        """Test the 'last_modified_by earlier than creation_time' rule."""
        metadata = self.clean_metadata.copy()
        # Set modified time to be one day before created time
        metadata['docx_core_properties']['modified'] = metadata['docx_core_properties']['created'] - timedelta(days=1)
        stats = DOCXStatistics(self.base_paragraphs, metadata, self.base_settings_rsids)
        result = stats.calculate_suspicion_score()
        self.assertIn("Document was last modified before it was created.", result['factors'])
        self.assertGreater(result['score'], 0)

    def test_missing_metadata_rule(self):
        """Test the 'missing metadata' rule for author, last_modified_by, and revision."""
        metadata = {
            'docx_core_properties': {
                'created': datetime(2023, 1, 1),
                'modified': datetime(2023, 1, 2),
                # Author, last_modified_by, and revision are missing
            },
            'core_properties': {}
        }
        stats = DOCXStatistics(self.base_paragraphs, metadata, self.base_settings_rsids)
        result = stats.calculate_suspicion_score()
        self.assertIn("Missing key metadata: Author, Last Modified By, Revision.", result['factors'][0])
        self.assertGreater(result['score'], 0)

    def test_missing_one_metadata_field(self):
        """Test that missing just one piece of metadata is detected."""
        metadata = self.clean_metadata.copy()
        del metadata['docx_core_properties']['revision']
        stats = DOCXStatistics(self.base_paragraphs, metadata, self.base_settings_rsids)
        result = stats.calculate_suspicion_score()
        self.assertIn("Missing key metadata: Revision.", result['factors'][0])
        self.assertGreater(result['score'], 0)

    def test_long_run_outlier_rule(self):
        """Test the 'long_run_outlier' rule using IQR."""
        # This data simulates a document with many short runs and one long one.
        # The IQR method should easily identify the 500-character run as an outlier.
        paragraphs_with_outlier = [
            {'runs': [{'text': 'Short.'}, {'text': 'Also short.'}] * 10}, # 20 short runs
            {'runs': [{'text': 'This is a very long run designed to be an outlier.' * 10}]}, # 1 long run (500 chars)
            {'runs': [{'text': 'Another short run.'}]} # 1 more short run
        ]
        # Use clean metadata so only this rule is triggered
        stats = DOCXStatistics(paragraphs_with_outlier, self.clean_metadata, self.base_settings_rsids)
        result = stats.calculate_suspicion_score()
        self.assertTrue(any("unusually long text run(s) detected" in factor for factor in result['factors']))
        self.assertGreater(result['score'], 0)

    def test_no_outliers_in_consistent_document(self):
        """Test that a document with consistently long runs does not trigger the outlier rule."""
        # All runs are consistently long, so none should be considered an outlier
        # relative to the others.
        paragraphs_consistent = [
            {'runs': [{'text': 'A long but consistent run.' * 5}] * 20} # 20 long runs
        ]
        stats = DOCXStatistics(paragraphs_consistent, self.clean_metadata, self.base_settings_rsids)
        result = stats.calculate_suspicion_score()
        self.assertFalse(any("unusually long text run(s) detected" in factor for factor in result['factors']))

    def test_writing_speed_rule(self):
        """Test the 'suspicious writing speed' rule (>200 WPM)."""
        # 1000 words in 2 minutes = 500 WPM (should be flagged)
        paragraphs = [
            {'runs': [{'text': 'word ' * 1000, 'rsid': '001'}]}
        ]
        metadata = self.clean_metadata.copy()
        metadata['docx_core_properties']['created'] = datetime(2023, 1, 1, 10, 0, 0)
        metadata['docx_core_properties']['modified'] = datetime(2023, 1, 1, 10, 2, 0)
        stats = DOCXStatistics(paragraphs, metadata, self.base_settings_rsids)
        result = stats.calculate_suspicion_score()
        self.assertTrue(any('Suspicious writing speed' in f for f in result['factors']))
        self.assertGreater(result['score'], 0)

    def test_rsid_density_per_document_rule(self):
        """Test the 'suspicious RSID density' rule (words per unique RSID > 500)."""
        # 1000 words, 1 RSID, should be flagged for high words/RSID
        paragraphs = [
            {'runs': [{'text': 'word ' * 1000, 'rsid': '001'}]}
        ]
        stats = DOCXStatistics(paragraphs, self.clean_metadata, {'rsids': [{'value': '001'}]})
        result = stats.calculate_suspicion_score()
        self.assertTrue(any('Suspicious RSID density' in f for f in result['factors']))
        self.assertGreater(result['score'], 0)

