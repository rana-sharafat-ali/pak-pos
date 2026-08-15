from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils.http import url_has_allowed_host_and_scheme
from .models import User
from .forms import (
    LoginForm,
    AdminUserCreationForm,
    UserUpdateForm,
    AdminResetUserPasswordForm,
    ChangeOwnPasswordForm
)
from django.conf import settings
from .decorators import admin_required


def login_view(request):
    """
    Dual Login view supporting Username or Email authentication with role-based routing
    """
    if request.user.is_authenticated:
        return redirect(request.user.get_redirect_url())

    next_url = request.GET.get('next', '')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data.get('username_or_email')
            password = form.cleaned_data.get('password')
            remember_me = form.cleaned_data.get('remember_me', True)

            # Check if account exists but is deactivated
            inactive_user = User.objects.filter(
                Q(username__iexact=identifier) | Q(email__iexact=identifier),
                is_active=False
            ).first()

            if inactive_user:
                messages.error(request, 'Your account has been deactivated. Please contact your administrator.')
            else:
                user = authenticate(request, username=identifier, password=password)
                if user is not None:
                    login(request, user)

                    # Dynamic session duration based on Remember Me
                    if remember_me:
                        request.session.set_expiry(settings.SESSION_COOKIE_AGE)
                    else:
                        request.session.set_expiry(0)

                    messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
                    
                    # Safe Next URL redirection
                    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                        return redirect(next_url)
                        
                    return redirect(user.get_redirect_url())
                else:
                    messages.error(request, 'Invalid username/email or password. Please try again.')
        else:
            messages.error(request, 'Please correct the errors in the login form.')
    else:
        form = LoginForm()

    context = {
        'form': form,
        'next': next_url,
        'title': 'Sign In',
    }
    return render(request, 'users/login.html', context)


def logout_view(request):
    """
    Log out user and redirect to login screen
    """
    if request.user.is_authenticated:
        name = request.user.get_full_name() or request.user.username
        logout(request)
        messages.success(request, f'Goodbye {name}, you have been signed out safely.')
    return redirect('users:login')


@admin_required
def user_list(request):
    """
    Admin-only User Management Table
    """
    query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    status_filter = request.GET.get('status', '').strip()

    users = User.objects.all().order_by('-date_joined')

    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(phone_number__icontains=query)
        )

    if role_filter:
        users = users.filter(role=role_filter)

    if status_filter:
        if status_filter == 'active':
            users = users.filter(is_active=True)
        elif status_filter == 'inactive':
            users = users.filter(is_active=False)

    context = {
        'users': users,
        'query': query,
        'selected_role': role_filter,
        'selected_status': status_filter,
        'roles': User.Role.choices,
        'title': 'Team & User Management',
    }
    return render(request, 'users/user_list.html', context)


@admin_required
def user_create(request):
    """
    Admin-only view to register a new staff / manager / admin member
    """
    if request.method == 'POST':
        form = AdminUserCreationForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            messages.success(request, f'User "{new_user.username}" ({new_user.get_role_display()}) registered successfully!')
            return redirect('users:user_list')
        else:
            messages.error(request, 'Please correct the errors in the form.')
    else:
        form = AdminUserCreationForm()

    context = {
        'form': form,
        'title': 'Add New Team Member',
        'is_create': True,
    }
    return render(request, 'users/user_form.html', context)


@admin_required
def user_update(request, pk):
    """
    Admin-only view to edit user account details
    """
    user_obj = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=user_obj, requesting_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'User "{user_obj.username}" updated successfully!')
            return redirect('users:user_list')
        else:
            messages.error(request, 'Please correct the errors in the form.')
    else:
        form = UserUpdateForm(instance=user_obj, requesting_user=request.user)

    context = {
        'form': form,
        'target_user': user_obj,
        'title': f'Edit Operator: {user_obj.username}',
        'is_create': False,
    }
    return render(request, 'users/user_form.html', context)


@admin_required
def user_reset_password(request, pk):
    """
    Admin-only view to directly change/reset any staff member's password
    """
    user_obj = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        form = AdminResetUserPasswordForm(request.POST)
        if form.is_valid():
            new_pass = form.cleaned_data.get('new_password')
            user_obj.set_password(new_pass)
            user_obj.save()
            messages.success(request, f'Password for "{user_obj.username}" has been successfully updated!')
            return redirect('users:user_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AdminResetUserPasswordForm()

    context = {
        'form': form,
        'target_user': user_obj,
        'title': f'Reset Password: {user_obj.username}',
        'is_self': False,
    }
    return render(request, 'users/change_password.html', context)


@login_required
def change_own_password(request):
    """
    Allows logged-in Admin or Staff to securely update their own password
    """
    if request.method == 'POST':
        form = ChangeOwnPasswordForm(request.POST, user=request.user)
        if form.is_valid():
            new_pass = form.cleaned_data.get('new_password')
            request.user.set_password(new_pass)
            request.user.save()
            update_session_auth_hash(request, request.user)  # Keep session active
            messages.success(request, 'Your password has been changed successfully!')
            return redirect(request.user.get_redirect_url())
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ChangeOwnPasswordForm(user=request.user)

    context = {
        'form': form,
        'target_user': request.user,
        'title': 'Change My Password',
        'is_self': True,
    }
    return render(request, 'users/change_password.html', context)


@admin_required
def user_toggle_status(request, pk):
    """
    Quickly toggle a user's active/inactive status
    """
    user_obj = get_object_or_404(User, pk=pk)
    
    if user_obj == request.user:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('users:user_list')

    if user_obj.role == User.Role.ADMIN and user_obj.is_active:
        active_admins = User.objects.filter(role=User.Role.ADMIN, is_active=True).exclude(pk=user_obj.pk)
        if not active_admins.exists():
            messages.error(request, 'Cannot deactivate the only active Administrator.')
            return redirect('users:user_list')

    user_obj.is_active = not user_obj.is_active
    user_obj.save()
    
    status_str = "activated" if user_obj.is_active else "deactivated"
    messages.success(request, f'User "{user_obj.username}" has been {status_str}.')
    return redirect('users:user_list')


@admin_required
def user_delete(request, pk):
    """
    Admin-only view to delete a user account
    """
    user_obj = get_object_or_404(User, pk=pk)
    
    if user_obj == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('users:user_list')

    if user_obj.role == User.Role.ADMIN:
        active_admins = User.objects.filter(role=User.Role.ADMIN, is_active=True).exclude(pk=user_obj.pk)
        if not active_admins.exists():
            messages.error(request, 'Cannot delete the only active Administrator.')
            return redirect('users:user_list')

    if request.method == 'POST':
        name = user_obj.username
        user_obj.delete()
        messages.success(request, f'User "{name}" deleted successfully.')
        
    return redirect('users:user_list')
