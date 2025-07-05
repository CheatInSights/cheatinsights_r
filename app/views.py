from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.core.mail import send_mail
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie

import io
import json
from collections import defaultdict

from .cis_extractor import Extract
from .cis_json_to_html import DocumentReconstructor
from .cis_statistics import DOCXStatistics


def home(request):
    """Home page view"""
    return render(request, 'app/home.html')

@login_required(login_url='/signin/')
def dashboard_page(request):
    """Render the dashboard page."""
    print(f"DEBUG: User authenticated: {request.user.is_authenticated}")
    print(f"DEBUG: User: {request.user}")
    print(f"DEBUG: Session ID: {request.session.session_key}")
    return render(request, 'app/dashboard/dashboard.html')


@csrf_exempt
def handle_multiple_uploads(request):
    """Handle multiple document uploads and process them for RSID analysis."""
    if request.method == 'POST':
        if 'documents' not in request.FILES:
            return JsonResponse({'error': 'No files uploaded'}, status=400)
        
        files = request.FILES.getlist('documents')
        if not files:
            return JsonResponse({'error': 'No files uploaded'}, status=400)
        
        print("\n========== DEBUG: SESSION FILE POST REQUEST ==========")
        print(f"Number of files uploaded: {len(files)}")
        
        # Validate all files are .docx
        for file in files:
            if not file.name.endswith('.docx'):
                return JsonResponse({'error': f'Only .docx files are allowed. Found: {file.name}'}, status=400)
        
        doc_data_list = []
        
        try:
            # --- First Pass: Extract data and create statistics objects ---
            for file in files:
                print(f"\tDEBUG: Processing file: {file.name}")
                file_content = file.read()
                file_obj = io.BytesIO(file_content)
                extractor = Extract(file_obj)
                
                # Gather all relevant data for this document
                doc_data = {
                    "filename": file.name,
                    "paragraphs": extractor.get_paragraphs(),
                    "settings_rsids": extractor.get_settings_rsids(),
                    "metadata": extractor.get_metadata(),
                    "statistics_obj": None # Placeholder for DOCXStatistics
                }
                
                # Create DOCXStatistics object for later analysis
                doc_data["statistics_obj"] = DOCXStatistics(
                    doc_data["paragraphs"], doc_data["metadata"], doc_data["settings_rsids"]
                )
                doc_data_list.append(doc_data)

            # --- Cross-Document Author Analysis ---
            author_to_docs = defaultdict(list)
            modifier_to_docs = defaultdict(list) # For the new rule
            for i, doc_data in enumerate(doc_data_list):
                author = doc_data["statistics_obj"].get_author()
                if author:
                    author_to_docs[author].append(i)
                
                modifier = doc_data["statistics_obj"].get_last_modified_by()
                if modifier:
                    modifier_to_docs[modifier].append(i)

            # Find authors/modifiers that appear in more than one document
            colluding_authors = {author: indices for author, indices in author_to_docs.items() if len(indices) > 1}
            colluding_modifiers = {modifier: indices for modifier, indices in modifier_to_docs.items() if len(indices) > 1}

            # --- Second Pass: Finalize results with cross-doc insights ---
            results = {}
            for i, doc_data in enumerate(doc_data_list):
                # Calculate the base suspicion score for this document
                # !!! obtains the per-document score (base score)
                suspicion_result = doc_data["statistics_obj"].calculate_suspicion_score()
                print(f"[DEBUG] {doc_data['filename']} - After per-document rules: total_score={suspicion_result['total_score']}, factors={suspicion_result['factors']}")

                # Cross-document Rule 1: Author Collusion
                # (Cross-document) Adds 30 if the same author appears in multiple uploaded documents
                author = doc_data["statistics_obj"].get_author()
                if author in colluding_authors:
                    suspicion_result['total_score'] += 30
                    suspicion_result['factors'].append(
                        f"Author '{author}' also appears in other uploaded documents (possible collusion)."
                    )
                    print(f"[DEBUG] {doc_data['filename']} - After author collusion: total_score={suspicion_result['total_score']}, factors={suspicion_result['factors']}")
                
                # Cross-document Rule 2: Modifier Collusion
                # (Cross-document) Adds 30 if the same last modified by appears in multiple uploaded documents
                modifier = doc_data["statistics_obj"].get_last_modified_by()
                if modifier in colluding_modifiers:
                    suspicion_result['total_score'] += 30
                    suspicion_result['factors'].append(
                        f"Editor '{modifier}' also appears in other uploaded documents (possible collusion)."
                    )
                    print(f"[DEBUG] {doc_data['filename']} - After modifier collusion: total_score={suspicion_result['total_score']}, factors={suspicion_result['factors']}")
                
                # Cross-document Rule 4: Author-Modifier Cross-Pollination
                # (Cross-document) Adds 25 if an author appears as a modifier in another document (and vice versa)
                author = doc_data["statistics_obj"].get_author()
                modifier = doc_data["statistics_obj"].get_last_modified_by()
                
                # Check if this author is a modifier in other docs
                if author and author in modifier_to_docs:
                    other_doc_indices = [idx for idx in modifier_to_docs[author] if idx != i]
                    if other_doc_indices:
                        suspicion_result['total_score'] += 25
                        suspicion_result['factors'].append(
                            f"Author '{author}' also appears as a modifier in other uploaded documents (possible collaboration)."
                        )
                        print(f"[DEBUG] {doc_data['filename']} - After author-modifier cross-pollination: total_score={suspicion_result['total_score']}, factors={suspicion_result['factors']}")
                
                # Check if this modifier is an author in other docs
                if modifier and modifier in author_to_docs:
                    other_doc_indices = [idx for idx in author_to_docs[modifier] if idx != i]
                    if other_doc_indices:
                        suspicion_result['total_score'] += 25
                        suspicion_result['factors'].append(
                            f"Modifier '{modifier}' also appears as an author in other uploaded documents (possible collaboration)."
                        )
                        print(f"[DEBUG] {doc_data['filename']} - After modifier-author cross-pollination: total_score={suspicion_result['total_score']}, factors={suspicion_result['factors']}")

                # Generate HTML for the document
                json_data = json.dumps(doc_data["paragraphs"], ensure_ascii=False)
                json_obj = io.StringIO(json_data)
                reconstructor = DocumentReconstructor(json_obj, document_name=doc_data["filename"])
                html_content = reconstructor.create_html()

                # Store final results for this document
                results[doc_data["filename"]] = {
                    'html': html_content,
                    'data': doc_data["paragraphs"],
                    'settings_rsids': doc_data["settings_rsids"],
                    'metadata': doc_data["metadata"],
                    'metrics': suspicion_result
                }

            # --- Cross-Document RSID Analysis ---
            # Build a mapping: filename -> set of RSIDs in that document
            doc_rsids = {doc["filename"]: set(rsid['value'] for rsid in doc["settings_rsids"].get('rsids', [])) for doc in doc_data_list}
            rsid_to_docs = defaultdict(set)
            for doc, rsids in doc_rsids.items():
                for rsid in rsids:
                    rsid_to_docs[rsid].add(doc)
            # Only keep RSIDs that appear in more than one document
            shared_rsids = {rsid: sorted(list(docs)) for rsid, docs in rsid_to_docs.items() if len(docs) > 1}

            # Build a mapping: doc_name -> set of shared RSIDs it contains
            doc_to_shared_rsids = {doc: set() for doc in results}
            for rsid, docs in shared_rsids.items():
                for doc in docs:
                    doc_to_shared_rsids[doc].add(rsid)

            # Cross-document Rule 3: RSID(s) appear in multiple documents
            for doc_name, shared in doc_to_shared_rsids.items():
                if shared:
                    results[doc_name]['metrics']['total_score'] += 30
                    results[doc_name]['metrics']['factors'].append(
                        f"RSID(s) {', '.join(shared)} appear in multiple documents (possible collusion)."
                    )
                    print(f"[DEBUG] {doc_name} - After RSID collusion: total_score={results[doc_name]['metrics']['total_score']}, factors={results[doc_name]['metrics']['factors']}")

            # Print final suspicion scores and factors for each document
            for doc_name, result in results.items():
                print(f"[DEBUG] FINAL {doc_name} - Total Score: {result['metrics']['total_score']}")
                print(f"[DEBUG] FINAL {doc_name} - Factors: {result['metrics']['factors']}")

            # --- Recalculate normalized score after all rules applied ---
            # Adjust this if you add/remove rules or change their weights
            max_possible_score = sum([15, 25, 15, 25, 20, 20, 30, 30, 30, 25])  # All rule weights: different_author, modified_before_created, missing_metadata, long_run_outlier, writing_speed, rsid_density, author collusion, modifier collusion, RSID collusion, author-modifier cross-pollination
            for doc_name, result in results.items():
                result['metrics']['score'] = round((result['metrics']['total_score'] / max_possible_score) * 100, 2)

            # Debug: Print final data structure being sent to frontend
            print("\n========== DEBUG: FINAL DATA BEING SENT TO FRONTEND ==========")
            for doc_name, result in results.items():
                print(f"\nDocument: {doc_name}")
                print(f"  Total Score: {result['metrics']['total_score']}")
                print(f"  Normalized Score: {result['metrics']['score']}%")
                print(f"  Factors: {result['metrics']['factors']}")
                print(f"  Max Possible Score: {max_possible_score}")
                print(f"  Calculation: {result['metrics']['total_score']} / {max_possible_score} * 100 = {result['metrics']['score']}%")

            # Return results for all files, and shared RSIDs
            return JsonResponse({
                'message': f'Successfully processed {len(files)} files',
                'results': results,
                'shared_rsids': shared_rsids
            }, status=200)

        except Exception as e:
            return JsonResponse({'error': f'Error processing files: {str(e)}'}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
@require_http_methods(["POST"])
def contact_submit(request):
    """
    Handle contact form submission and send email
    """
    try:
        data = json.loads(request.body)
        
        # Extract form data
        name = data.get('name', '')
        organization = data.get('organization', '')
        email = data.get('emailAddress', '')
        inquiry_type = data.get('inquiryType', '')
        student_count = data.get('studentCount', '')
        message = data.get('message', '')
        
        # Validate required fields
        if not all([name, organization, email, inquiry_type, message]):
            return JsonResponse({
                'success': False,
                'message': 'Please fill in all required fields.'
            }, status=400)
        
        # Prepare email content
        subject = f"CheatInSights Contact: {inquiry_type.title()} - {name}"
        
        email_body = f"""
New Contact Form Submission

Name: {name}
Organization: {organization}
Email: {email}
Inquiry Type: {inquiry_type}
Student Count: {student_count}

Message:
{message}

---
This message was sent from the CheatInSights contact form.
        """
        
        # Send email
        try:
            send_mail(
                subject=subject,
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.CONTACT_EMAIL],  # Configure this in settings
                fail_silently=False,
            )
        except Exception as email_error:
            # Log the email error but don't crash the application
            print(f"EMAIL ERROR: {email_error}")
            # Still return success to user, but log the issue
            # In production, you might want to send this to a logging service
            # You could also store the message in a database for later processing
        
        return JsonResponse({
            'success': True,
            'message': 'Thank you for your message! We will get back to you soon.'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid form data.'
        }, status=400)
    except Exception as e:
        import traceback
        print("EMAIL ERROR:", e)
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'An error occurred while sending your message: {e}'
        }, status=500)


def contact(request):
    """
    Render the contact page
    """
    return render(request, 'app/contact.html')


def documentation(request):
    """
    Render the documentation page
    """
    return render(request, 'app/documentation.html')


def company(request):
    """
    Render the company page
    """
    return render(request, 'app/company.html')

@ensure_csrf_cookie
def signin(request):
    """
    Handle signin page rendering and authentication
    """
    # Redirect authenticated users to dashboard
    if request.user.is_authenticated:
        return redirect('/dashboard/')
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username', '').strip()
            password = data.get('password', '')
            remember_me = data.get('rememberMe', False)
            
            # Validate required fields
            if not username or not password:
                return JsonResponse({
                    'success': False,
                    'message': 'Please provide both username and password.'
                }, status=400)
            
            # Authenticate user
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                # Login successful
                login(request, user)
                
                # Handle remember me functionality
                if not remember_me:
                    # Set session to expire when browser closes
                    request.session.set_expiry(0)
                    session_expiry_time = request.session.get_expiry_age()
                    print(f"DEBUG: Session expiry time (in seconds): {session_expiry_time}")
                else:
                    # Set session to expire based on configured duration
                    remember_me_duration = getattr(settings, 'REMEMBER_ME_DURATION', 30 * 24 * 60 * 60)
                    request.session.set_expiry(remember_me_duration)
                
                return JsonResponse({
                    'success': True,
                    'message': 'Login successful',
                    'redirect_url': '/dashboard/'
                })
            else:
                # Authentication failed
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid username or password.'
                }, status=401)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid request data.'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': 'An error occurred during authentication.'
            }, status=500)
    
    # GET request - render signin page
    return render(request, 'app/signin.html')


def signout(request):
    """
    Handle signout and logout with comprehensive session cleanup
    """
    # Logout the user (this handles Django's authentication)
    logout(request)
    
    # Clear session data
    request.session.flush()
    
    # Create response to redirect to home
    response = redirect('/')
    
    # Clear any custom cookies that might exist
    response.delete_cookie('sessionid')
    response.delete_cookie('csrftoken')
    
    # Set session cookie to expire immediately
    response.set_cookie('sessionid', '', max_age=0, expires='Thu, 01 Jan 1970 00:00:00 GMT')
    
    return response

