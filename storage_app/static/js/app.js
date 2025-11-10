// Enhanced drag and drop functionality
document.addEventListener('DOMContentLoaded', function() {
    initializeEnhancedInteractions();
});

function initializeEnhancedInteractions() {
    // Enhanced drag and drop
    const uploadArea = document.querySelector('.upload-area');
    const fileInput = document.getElementById('file');
    
    if (uploadArea && fileInput) {
        setupDragAndDrop(uploadArea, fileInput);
    }
    
    // Add hover effects to all interactive elements
    addHoverEffects();
    
    // Initialize tooltips
    initializeTooltips();
    
    // Add loading states to forms
    initializeFormLoadingStates();
}

function setupDragAndDrop(uploadArea, fileInput) {
    const events = ['dragenter', 'dragover', 'dragleave', 'drop'];
    
    events.forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });
    
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, unhighlight, false);
    });
    
    uploadArea.addEventListener('drop', handleDrop, false);
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    function highlight() {
        uploadArea.classList.add('dragover', 'scale-105');
        uploadArea.style.borderColor = '#3b82f6';
        uploadArea.style.backgroundColor = 'rgba(239, 246, 255, 0.7)';
    }
    
    function unhighlight() {
        uploadArea.classList.remove('dragover', 'scale-105');
        uploadArea.style.borderColor = '';
        uploadArea.style.backgroundColor = '';
    }
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        fileInput.files = files;
        
        // Show file preview
        if (files.length > 0) {
            showFilePreview(files[0]);
        }
    }
}

function showFilePreview(file) {
    const uploadArea = document.querySelector('.upload-area');
    if (!uploadArea) return;
    
    const fileSize = formatFileSize(file.size);
    const fileName = file.name;
    const fileType = fileName.split('.').pop().toUpperCase();
    
    uploadArea.innerHTML = `
        <div class="flex flex-col items-center justify-center text-center">
            <div class="w-16 h-16 bg-green-100 rounded-2xl flex items-center justify-center mb-3">
                <i class="fas fa-file text-green-600 text-2xl"></i>
            </div>
            <p class="font-semibold text-gray-700 text-lg mb-1">${fileName}</p>
            <p class="text-gray-500 text-sm">${fileType} • ${fileSize}</p>
            <p class="text-green-600 text-sm font-medium mt-2">
                <i class="fas fa-check-circle mr-1"></i>Ready to upload
            </p>
        </div>
    `;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function addHoverEffects() {
    // Add hover effects to cards
    const cards = document.querySelectorAll('.glass-card, .file-card, .folder-item');
    cards.forEach(card => {
        card.style.transition = 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
        
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px) scale(1.02)';
            this.style.boxShadow = '0 20px 40px rgba(0, 0, 0, 0.1)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0px) scale(1)';
            this.style.boxShadow = '';
        });
    });
    
    // Add hover effects to buttons
    const buttons = document.querySelectorAll('button, .btn-gradient, a[href]');
    buttons.forEach(button => {
        button.style.transition = 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)';
        
        button.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
        });
        
        button.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0px)';
        });
    });
}

function initializeTooltips() {
    // Add tooltip functionality to elements with title attribute
    const elementsWithTitle = document.querySelectorAll('[title]');
    elementsWithTitle.forEach(element => {
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
    });
}

function showTooltip(e) {
    const tooltip = document.createElement('div');
    tooltip.className = 'fixed z-50 px-3 py-2 text-sm text-white bg-gray-900 rounded-lg shadow-lg';
    tooltip.textContent = this.getAttribute('title');
    tooltip.id = 'tooltip';
    
    document.body.appendChild(tooltip);
    
    // Position tooltip
    const rect = this.getBoundingClientRect();
    tooltip.style.left = rect.left + 'px';
    tooltip.style.top = (rect.top - tooltip.offsetHeight - 5) + 'px';
}

function hideTooltip() {
    const tooltip = document.getElementById('tooltip');
    if (tooltip) {
        tooltip.remove();
    }
}

function initializeFormLoadingStates() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.classList.add('loading');
                submitBtn.disabled = true;
                
                // Re-enable button after 10 seconds (safety net)
                setTimeout(() => {
                    submitBtn.classList.remove('loading');
                    submitBtn.disabled = false;
                }, 10000);
            }
        });
    });
}

// Enhanced notification system
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    const types = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        warning: 'bg-yellow-500',
        info: 'bg-blue-500'
    };
    
    notification.className = `fixed top-4 right-4 ${types[type]} text-white px-6 py-4 rounded-2xl shadow-2xl z-50 transform transition-all duration-300 translate-x-full`;
    notification.innerHTML = `
        <div class="flex items-center space-x-3">
            <i class="fas fa-${getNotificationIcon(type)}"></i>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.classList.remove('translate-x-full');
    }, 10);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        notification.classList.add('translate-x-full');
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

function getNotificationIcon(type) {
    const icons = {
        success: 'check-circle',
        error: 'exclamation-circle',
        warning: 'exclamation-triangle',
        info: 'info-circle'
    };
    return icons[type] || 'info-circle';
}

// Enhanced file operations with feedback
function enhancedDeleteFile(fileId, element) {
    if (confirm('Are you sure you want to delete this file? This action cannot be undone.')) {
        // Add loading state to the button
        const deleteBtn = element.closest('button');
        const originalHtml = deleteBtn.innerHTML;
        deleteBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        deleteBtn.disabled = true;
        
        fetch(`/delete/${fileId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json',
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('File deleted successfully', 'success');
                // Animate removal
                const fileElement = element.closest('.file-item') || element.closest('.file-card');
                if (fileElement) {
                    fileElement.style.opacity = '0';
                    fileElement.style.transform = 'translateX(100px)';
                    setTimeout(() => fileElement.remove(), 500);
                } else {
                    setTimeout(() => location.reload(), 1000);
                }
            } else {
                throw new Error(data.error || 'Failed to delete file');
            }
        })
        .catch(error => {
            showNotification('Error deleting file: ' + error.message, 'error');
            deleteBtn.innerHTML = originalHtml;
            deleteBtn.disabled = false;
        });
    }
}

function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}

// Export functions for global use
window.enhancedDeleteFile = enhancedDeleteFile;
window.showNotification = showNotification;
window.formatFileSize = formatFileSize;


// Task Management Functions
function initializeTaskManagement() {
    // Add task-specific event listeners and initialization
    initializeTaskModals();
    initializeTaskFilters();
}

function initializeTaskModals() {
    // Close modals on outside click
    document.addEventListener('click', function(e) {
        if (e.target.id === 'createTaskModal') {
            closeCreateTaskModal();
        }
        if (e.target.id === 'editTaskModal') {
            closeEditTaskModal();
        }
    });

    // Escape key to close modals
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeCreateTaskModal();
            closeEditTaskModal();
        }
    });
}

function initializeTaskFilters() {
    // Initialize any task-specific filter functionality
    console.log('Task filters initialized');
}

// Task API Functions
async function createTask(formData) {
    try {
        const response = await fetch('/tasks/create/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            }
        });
        return await response.json();
    } catch (error) {
        console.error('Error creating task:', error);
        return { success: false, error: 'Network error' };
    }
}

async function updateTask(taskId, formData) {
    try {
        const response = await fetch(`/tasks/${taskId}/edit/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            }
        });
        return await response.json();
    } catch (error) {
        console.error('Error updating task:', error);
        return { success: false, error: 'Network error' };
    }
}

async function toggleTaskStatus(taskId) {
    try {
        const response = await fetch(`/tasks/${taskId}/toggle/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json',
            },
        });
        return await response.json();
    } catch (error) {
        console.error('Error toggling task status:', error);
        return { success: false, error: 'Network error' };
    }
}

async function deleteTask(taskId) {
    try {
        const response = await fetch(`/tasks/${taskId}/delete/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json',
            },
        });
        return await response.json();
    } catch (error) {
        console.error('Error deleting task:', error);
        return { success: false, error: 'Network error' };
    }
}

// Enhanced task functions with better UX
function enhancedCreateTask(formElement) {
    const submitBtn = formElement.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    
    // Show loading state
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Creating...';
    submitBtn.disabled = true;
    
    const formData = new FormData(formElement);
    
    createTask(formData)
        .then(data => {
            if (data.success) {
                showNotification('Task created successfully', 'success');
                closeCreateTaskModal();
                setTimeout(() => location.reload(), 1000);
            } else {
                showNotification('Error creating task: ' + data.error, 'error');
            }
        })
        .finally(() => {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        });
}

function enhancedUpdateTask(taskId, formElement) {
    const submitBtn = formElement.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    
    // Show loading state
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Updating...';
    submitBtn.disabled = true;
    
    const formData = new FormData(formElement);
    
    updateTask(taskId, formData)
        .then(data => {
            if (data.success) {
                showNotification('Task updated successfully', 'success');
                closeEditTaskModal();
                setTimeout(() => location.reload(), 1000);
            } else {
                showNotification('Error updating task: ' + data.error, 'error');
            }
        })
        .finally(() => {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        });
}

function enhancedToggleTaskStatus(taskId, element) {
    const originalHtml = element.innerHTML;
    element.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    element.disabled = true;
    
    toggleTaskStatus(taskId)
        .then(data => {
            if (data.success) {
                showNotification(`Task marked as ${data.status_display}`, 'success');
                // Animate the change
                const taskItem = element.closest('.task-item');
                if (taskItem) {
                    taskItem.style.opacity = '0.7';
                    setTimeout(() => {
                        location.reload();
                    }, 500);
                } else {
                    setTimeout(() => location.reload(), 500);
                }
            } else {
                throw new Error(data.error || 'Failed to update task status');
            }
        })
        .catch(error => {
            showNotification('Error updating task status: ' + error.message, 'error');
            element.innerHTML = originalHtml;
            element.disabled = false;
        });
}

function enhancedDeleteTask(taskId, element) {
    if (confirm('Are you sure you want to delete this task? This action cannot be undone.')) {
        const originalHtml = element.innerHTML;
        element.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        element.disabled = true;
        
        deleteTask(taskId)
            .then(data => {
                if (data.success) {
                    showNotification('Task deleted successfully', 'success');
                    // Animate removal
                    const taskElement = element.closest('.task-item');
                    if (taskElement) {
                        taskElement.style.opacity = '0';
                        taskElement.style.transform = 'translateX(100px)';
                        setTimeout(() => taskElement.remove(), 500);
                    } else {
                        setTimeout(() => location.reload(), 1000);
                    }
                } else {
                    throw new Error(data.error || 'Failed to delete task');
                }
            })
            .catch(error => {
                showNotification('Error deleting task: ' + error.message, 'error');
                element.innerHTML = originalHtml;
                element.disabled = false;
            });
    }
}

// Export task functions for global use
window.enhancedCreateTask = enhancedCreateTask;
window.enhancedUpdateTask = enhancedUpdateTask;
window.enhancedToggleTaskStatus = enhancedToggleTaskStatus;
window.enhancedDeleteTask = enhancedDeleteTask;
window.initializeTaskManagement = initializeTaskManagement;

// Initialize task management when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeTaskManagement();
});