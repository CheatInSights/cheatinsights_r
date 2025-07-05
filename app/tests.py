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


class CrossDocumentRulesTests(TestCase):
    """Test the cross-document suspicion rules that are implemented in views.py"""
    
    def setUp(self):
        """Set up test data for cross-document rule testing."""
        self.base_metadata = {
            'docx_core_properties': {
                'created': datetime(2023, 1, 1),
                'modified': datetime(2023, 1, 2),
                'revision': '1',
            },
            'core_properties': {}
        }

    def create_doc_stats(self, author, modifier, rsids, paragraphs=None):
        """Helper method to create DOCXStatistics objects for testing."""
        if paragraphs is None:
            paragraphs = [{'runs': [{'text': 'Test content', 'rsid': rsids[0]}]}]
        
        metadata = {
            'docx_core_properties': {
                'author': author,
                'last_modified_by': modifier,
                'created': datetime(2023, 1, 1),
                'modified': datetime(2023, 1, 2),
                'revision': '1',
            },
            'core_properties': {}  # Empty to avoid conflicts
        }
        
        settings_rsids = {'rsids': [{'value': rsid} for rsid in rsids]}
        
        return DOCXStatistics(paragraphs, metadata, settings_rsids)

    def test_author_collusion_rule(self):
        """Test that documents with the same author trigger the author collusion rule."""
        # Create two documents with the same author
        doc1 = self.create_doc_stats('Student A', 'Student A', ['RSID1'])
        doc2 = self.create_doc_stats('Student A', 'Student B', ['RSID2'])
        
        # Simulate the author collusion logic from views.py
        from collections import defaultdict
        doc_data_list = [
            {'statistics_obj': doc1, 'filename': 'doc1.docx'},
            {'statistics_obj': doc2, 'filename': 'doc2.docx'}
        ]
        
        # Build author mapping
        author_to_docs = defaultdict(list)
        for i, doc_data in enumerate(doc_data_list):
            author = doc_data["statistics_obj"].get_author()
            if author:
                author_to_docs[author].append(i)
        
        # Find colluding authors
        colluding_authors = {author: indices for author, indices in author_to_docs.items() if len(indices) > 1}
        
        # Test that Student A is flagged as colluding
        self.assertIn('Student A', colluding_authors)
        self.assertEqual(len(colluding_authors['Student A']), 2)
        self.assertEqual(set(colluding_authors['Student A']), {0, 1})

    def test_modifier_collusion_rule(self):
        """Test that documents with the same modifier trigger the modifier collusion rule."""
        # Create two documents with the same modifier
        doc1 = self.create_doc_stats('Student A', 'Student X', ['RSID1'])
        doc2 = self.create_doc_stats('Student B', 'Student X', ['RSID2'])
        
        # Simulate the modifier collusion logic from views.py
        from collections import defaultdict
        doc_data_list = [
            {'statistics_obj': doc1, 'filename': 'doc1.docx'},
            {'statistics_obj': doc2, 'filename': 'doc2.docx'}
        ]
        
        # Build modifier mapping
        modifier_to_docs = defaultdict(list)
        for i, doc_data in enumerate(doc_data_list):
            modifier = doc_data["statistics_obj"].get_last_modified_by()
            if modifier:
                modifier_to_docs[modifier].append(i)
        
        # Find colluding modifiers
        colluding_modifiers = {modifier: indices for modifier, indices in modifier_to_docs.items() if len(indices) > 1}
        
        # Test that Student X is flagged as colluding
        self.assertIn('Student X', colluding_modifiers)
        self.assertEqual(len(colluding_modifiers['Student X']), 2)
        self.assertEqual(set(colluding_modifiers['Student X']), {0, 1})

    def test_rsid_collusion_rule(self):
        """Test that documents with shared RSIDs trigger the RSID collusion rule."""
        # Create two documents with the same RSID
        doc1 = self.create_doc_stats('Student A', 'Student A', ['SHARED_RSID'])
        doc2 = self.create_doc_stats('Student B', 'Student B', ['SHARED_RSID'])
        
        # Simulate the RSID collusion logic from views.py
        from collections import defaultdict
        doc_data_list = [
            {'filename': 'doc1.docx', 'settings_rsids': doc1.settings_rsids},
            {'filename': 'doc2.docx', 'settings_rsids': doc2.settings_rsids}
        ]
        
        # Build RSID mapping
        doc_rsids = {doc['filename']: set(rsid['value'] for rsid in doc['settings_rsids'].get('rsids', [])) for doc in doc_data_list}
        rsid_to_docs = defaultdict(set)
        for doc, rsids in doc_rsids.items():
            for rsid in rsids:
                rsid_to_docs[rsid].add(doc)
        
        # Find shared RSIDs
        shared_rsids = {rsid: sorted(list(docs)) for rsid, docs in rsid_to_docs.items() if len(docs) > 1}
        
        # Test that SHARED_RSID is flagged as shared
        self.assertIn('SHARED_RSID', shared_rsids)
        self.assertEqual(set(shared_rsids['SHARED_RSID']), {'doc1.docx', 'doc2.docx'})

    def test_author_modifier_cross_pollination_rule(self):
        """Test that author-modifier cross-pollination is detected."""
        # Create documents where author of one is modifier of another
        # Doc1: Student A is author
        # Doc2: Student A is modifier (cross-pollination)
        doc1 = self.create_doc_stats('Student A', 'Student A', ['RSID1'])
        doc2 = self.create_doc_stats('Student B', 'Student A', ['RSID2'])  # Student A is modifier here
        
        # Simulate the cross-pollination logic from views.py
        from collections import defaultdict
        doc_data_list = [
            {'statistics_obj': doc1, 'filename': 'doc1.docx'},
            {'statistics_obj': doc2, 'filename': 'doc2.docx'}
        ]
        
        # Build mappings
        author_to_docs = defaultdict(list)
        modifier_to_docs = defaultdict(list)
        for i, doc_data in enumerate(doc_data_list):
            author = doc_data["statistics_obj"].get_author()
            modifier = doc_data["statistics_obj"].get_last_modified_by()
            if author:
                author_to_docs[author].append(i)
            if modifier:
                modifier_to_docs[modifier].append(i)
        
        # Test author-modifier cross-pollination
        # Student A should be author in doc1 and modifier in doc2
        self.assertIn('Student A', author_to_docs)
        self.assertIn('Student A', modifier_to_docs)
        
        # Check that Student A appears as author in one doc and modifier in another
        author_indices = author_to_docs['Student A']
        modifier_indices = modifier_to_docs['Student A']
        
        # Should have cross-pollination (Student A is author in one doc, modifier in another)
        self.assertTrue(len(author_indices) >= 1 and len(modifier_indices) >= 1)
        # The indices should be different (not the same document)
        self.assertNotEqual(set(author_indices), set(modifier_indices))

    def test_no_collusion_in_clean_documents(self):
        """Test that documents with different authors, modifiers, and RSIDs don't trigger collusion rules."""
        # Create documents with completely different metadata - no shared authors or modifiers
        doc1 = self.create_doc_stats('Student A', 'Modifier X', ['RSID1'])
        doc2 = self.create_doc_stats('Student B', 'Modifier Y', ['RSID2'])
        doc3 = self.create_doc_stats('Student C', 'Modifier Z', ['RSID3'])
        
        from collections import defaultdict
        doc_data_list = [
            {'statistics_obj': doc1, 'filename': 'doc1.docx'},
            {'statistics_obj': doc2, 'filename': 'doc2.docx'},
            {'statistics_obj': doc3, 'filename': 'doc3.docx'}
        ]
        
        # Build mappings
        author_to_docs = defaultdict(list)
        modifier_to_docs = defaultdict(list)
        for i, doc_data in enumerate(doc_data_list):
            author = doc_data["statistics_obj"].get_author()
            modifier = doc_data["statistics_obj"].get_last_modified_by()
            if author:
                author_to_docs[author].append(i)
            if modifier:
                modifier_to_docs[modifier].append(i)
        
        # Find colluding authors/modifiers
        colluding_authors = {author: indices for author, indices in author_to_docs.items() if len(indices) > 1}
        colluding_modifiers = {modifier: indices for modifier, indices in modifier_to_docs.items() if len(indices) > 1}
        
        # Should have no collusion
        self.assertEqual(len(colluding_authors), 0)
        self.assertEqual(len(colluding_modifiers), 0)
        
        # Test RSID collusion
        doc_rsids = {doc['filename']: set(rsid['value'] for rsid in doc['statistics_obj'].settings_rsids.get('rsids', [])) for doc in doc_data_list}
        rsid_to_docs = defaultdict(set)
        for doc, rsids in doc_rsids.items():
            for rsid in rsids:
                rsid_to_docs[rsid].add(doc)
        
        shared_rsids = {rsid: sorted(list(docs)) for rsid, docs in rsid_to_docs.items() if len(docs) > 1}
        
        # Should have no shared RSIDs
        self.assertEqual(len(shared_rsids), 0)

