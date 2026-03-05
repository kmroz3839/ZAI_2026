from django.db import models

# Create your models here.

class Project(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
    
    def __str__(self):
        return self.name

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

class Task(models.Model):
    class Status(models.TextChoices):
        TODO = 'todo', 'To do'
        DOING = 'doing', 'Doing'
        DONE = 'done', 'Done'

    project = models.ForeignKey(
        Project, 
        on_delete=models.CASCADE, 
        related_name='tasks'
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.TODO
    )

    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    tags = models.ManyToManyField(
        Tag, 
        blank=True,
        related_name='tasks'
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title