from django.shortcuts import render
from django.http import HttpResponse
from datetime import datetime

def home(request):
    """Home page view"""
    context = {
        'current_time': datetime.now().strftime("%B %d, %Y at %I:%M %p")
    }
    return render(request, 'app/home.html', context)


def upload_page(request):
    return render(request, 'app/upload.html')