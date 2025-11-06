from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import File, Folder

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

class FileUploadForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ['file', 'is_public']
        
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Check file size (max 100MB)
            if file.size > 100 * 1024 * 1024:
                raise forms.ValidationError("File size must be under 100MB")
        return file

class FileShareForm(forms.Form):
    expires_in = forms.ChoiceField(
        choices=[
            (1, "1 day"),
            (7, "1 week"),
            (30, "1 month"),
            (None, "Never")
        ],
        required=False
    )

class FolderCreateForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Enter folder name'
            })
        }

class MoveFileForm(forms.Form):
    folder = forms.ModelChoiceField(
        queryset=Folder.objects.none(),
        required=False,
        empty_label="Root (No Folder)",
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
        })
    )
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['folder'].queryset = Folder.objects.filter(owner=user).order_by('name')