from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .cis_extractor import Extract
from .cis_json_to_html import DocumentReconstructor
import io
import json

def home(request):
    """Home page view"""
    return render(request, 'app/home.html')


def upload_page(request):
    return render(request, 'app/upload.html')


@csrf_exempt
def handle_multiple_uploads(request):
    if request.method == 'POST':
        if 'documents' not in request.FILES:
            return JsonResponse({'error': 'No files uploaded'}, status=400)
        
        files = request.FILES.getlist('documents')
        if not files:
            return JsonResponse({'error': 'No files uploaded'}, status=400)
        
        print("\n========== DEBUG: PROCESSING MULTIPLE FILES ==========")
        print(f"Number of files uploaded: {len(files)}")
        
        # Validate all files are .docx
        for file in files:
            if not file.name.endswith('.docx'):
                return JsonResponse({'error': f'Only .docx files are allowed. Found: {file.name}'}, status=400)
        
        results = {}
        doc_rsids = {}  # Map: filename -> set of RSIDs
        
        try:
            for file in files:
                print(f"\nProcessing file: {file.name}")
                # Read file content into memory
                file_content = file.read()
                
                # Create a BytesIO object to simulate a file
                file_obj = io.BytesIO(file_content)
                
                # Process the file using Extract class
                extractor = Extract(file_obj)
                paragraphs = extractor.get_paragraphs()
                settings_rsids = extractor.get_settings_rsids()
                metadata = extractor.get_metadata()

                # Convert paragraphs to JSON string
                json_data = json.dumps(paragraphs, ensure_ascii=False)
                
                # Create a StringIO object for JSON data
                json_obj = io.StringIO(json_data)
                
                # Generate color-coded HTML with document name for unique RSID handling
                reconstructor = DocumentReconstructor(json_obj, document_name=file.name)
                html_content = reconstructor.create_html()

                # Store results for this file
                results[file.name] = {
                    'html': html_content,
                    'data': paragraphs,
                    'settings_rsids': settings_rsids,
                    'metadata': metadata
                }

                # Collect RSIDs for this document
                doc_rsids[file.name] = set(rsid['value'] for rsid in settings_rsids.get('rsids', []))
                print(f"Found {len(doc_rsids[file.name])} unique RSIDs in {file.name}")

            # Build mapping from RSID to set of documents
            from collections import defaultdict
            rsid_to_docs = defaultdict(set)
            for doc, rsids in doc_rsids.items():
                for rsid in rsids:
                    rsid_to_docs[rsid].add(doc)
            
            # Only keep RSIDs that appear in more than one document
            shared_rsids = {rsid: sorted(list(docs)) for rsid, docs in rsid_to_docs.items() if len(docs) > 1}

            print("\n========== DEBUG: SHARED RSIDs ANALYSIS ==========")
            if shared_rsids:
                print(f"Found {len(shared_rsids)} RSIDs that appear in multiple documents:")
                for rsid, documents in shared_rsids.items():
                    print(f"\nRSID: {rsid}")
                    print(f"Appears in {len(documents)} documents:")
                    for doc in documents:
                        print(f"  - {doc}")
            else:
                print("No shared RSIDs found between documents.")
            print("===============================================\n")

            # Return results for all files, and shared RSIDs
            return JsonResponse({
                'message': f'Successfully processed {len(files)} files',
                'results': results,
                'shared_rsids': shared_rsids
            }, status=200)

        except Exception as e:
            print(f"\nERROR: {str(e)}")
            return JsonResponse({
                'error': f'Error processing files: {str(e)}'
            }, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)