from django.shortcuts import render


def home(request):
    """
    Main Landing / Dashboard View (Core App)
    """
    return render(request, 'core/index.html')
