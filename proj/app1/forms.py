from django import forms
from .models import Task, Project

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'status', 'project', 'due_date', 'tags']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'tags': forms.CheckboxSelectMultiple(),
        }
    
    def clean_title(self):
        title = self.cleaned_data['title']

        if "test" in title.lower():
            raise forms.ValidationError("tytuł nie może zawierać słowa test")
        
        return title

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']