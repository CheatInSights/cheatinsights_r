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

            # --- Cross-Document RSID Density Analysis ---
            # Calculate RSID density for each document
            rsid_densities = []
            chars_per_run_list = []  # For batch outlier rule
            for doc_data in doc_data_list:
                unique_rsid_count = len(doc_data["statistics_obj"].char_per_unique_rsid)
                word_count = doc_data["statistics_obj"].word_count
                total_characters = sum(doc_data["statistics_obj"].char_per_run)
                total_runs = len(doc_data["statistics_obj"].char_per_run)
                if unique_rsid_count > 0 and word_count > 0:
                    density = word_count / unique_rsid_count
                    rsid_densities.append(density)
                # Calculate characters per run for each document
                if total_runs > 0:
                    chars_per_run = total_characters / total_runs
                    chars_per_run_list.append(chars_per_run)
                else:
                    chars_per_run_list.append(0)
            
            # Calculate statistical outliers if we have multiple documents with valid densities
            rsid_density_outliers = set()
            chars_per_run_outliers = set()
            if len(rsid_densities) > 1:
                import statistics
                mean_density = statistics.mean(rsid_densities)
                std_dev = statistics.stdev(rsid_densities) if len(rsid_densities) > 1 else 0
                
                # Flag documents more than 2 standard deviations above the mean
                threshold = mean_density + (2 * std_dev)
                
                for i, doc_data in enumerate(doc_data_list):
                    unique_rsid_count = len(doc_data["statistics_obj"].char_per_unique_rsid)
                    word_count = doc_data["statistics_obj"].word_count
                    if unique_rsid_count > 0 and word_count > 0:
                        density = word_count / unique_rsid_count
                        if density > threshold:
                            rsid_density_outliers.add(i)
            # Batch outlier rule for characters per run
            if len(chars_per_run_list) > 1:
                import statistics
                mean_chars_per_run = statistics.mean(chars_per_run_list)
                std_chars_per_run = statistics.stdev(chars_per_run_list) if len(chars_per_run_list) > 1 else 0
                chars_per_run_threshold = mean_chars_per_run + (2 * std_chars_per_run)
                for i, chars_per_run in enumerate(chars_per_run_list):
                    if chars_per_run > chars_per_run_threshold:
                        chars_per_run_outliers.add(i)

            # --- Second Pass: Finalize results with cross-doc insights ---
            results = {}
            for i, doc_data in enumerate(doc_data_list):
                # Calculate the base suspicion score for this document
                suspicion_result = doc_data["statistics_obj"].calculate_suspicion_score()
                print(f"[DEBUG] {doc_data['filename']} - After per-document rules: total_score={suspicion_result['total_score']}, factors={suspicion_result['factors']}")

                # Cross-document Rule 1: Author appears in multiple documents
                author = doc_data["statistics_obj"].get_author()
                if author in colluding_authors:
                    suspicion_result['total_score'] += 30
                    suspicion_result['factors'].append(
                        f"Author '{author}' also appears in other uploaded documents (possible collusion)."
                    )
                    print(f"[DEBUG] {doc_data['filename']} - After author collusion: total_score={suspicion_result['total_score']}, factors={suspicion_result['factors']}")
                
                # Cross-document Rule 2: 'Last Modified By' appears in multiple documents
                modifier = doc_data["statistics_obj"].get_last_modified_by()
                if modifier in colluding_modifiers:
                    suspicion_result['total_score'] += 30
                    suspicion_result['factors'].append(
                        f"Editor '{modifier}' also appears in other uploaded documents (possible collusion)."
                    )
                    print(f"[DEBUG] {doc_data['filename']} - After modifier collusion: total_score={suspicion_result['total_score']}, factors={suspicion_result['factors']}")
                
                # Cross-document Rule 3: RSID density outlier compared to batch
                if i in rsid_density_outliers:
                    suspicion_result['total_score'] += 20
                    suspicion_result['factors'].append(
                        f"RSID density is suspiciously high compared to other documents in this batch (possible copy-pasting)."
                    )
                    print(f"[DEBUG] {doc_data['filename']} - After RSID density outlier: total_score={suspicion_result['total_score']}, factors={suspicion_result['factors']}")

                # Cross-document Rule 4: Characters per run outlier compared to batch
                if i in chars_per_run_outliers:
                    suspicion_result['total_score'] += 15
                    suspicion_result['factors'].append(
                        f"Characters per run is much higher than other documents in this batch (possible copy-pasting or bulk writing)."
                    )
                    print(f"[DEBUG] {doc_data['filename']} - After chars per run outlier: total_score={suspicion_result['total_score']}, factors={suspicion_result['factors']}")

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
            max_possible_score = sum([15, 25, 15, 25, 20, 20, 30, 30, 30, 20, 15])  # All rule weights: different_author, modified_before_created, missing_metadata, long_run_outlier, writing_speed, rsid_density, author collusion, modifier collusion, RSID collusion, cross-doc RSID density, cross-doc chars per run
            for doc_name, result in results.items():
                result['metrics']['score'] = round((result['metrics']['total_score'] / max_possible_score) * 100, 2)

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
        send_mail(
            subject=subject,
            message=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.CONTACT_EMAIL],  # Configure this in settings
            fail_silently=False,
        )
        
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
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while sending your message. Please try again.'
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

