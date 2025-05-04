// Main JavaScript file for نقطة وصل

// Initialize tooltips and popovers
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize Bootstrap popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    $('.alert').delay(5000).fadeOut('slow');

    // Image preview for product form
    handleImagePreview();

    // Handle favorite buttons
    handleFavoriteButtons();

    // Handle image gallery in product view
    handleImageGallery();

    // Handle chat functionality
    handleChat();

    // Handle search filters
    handleSearchFilters();

    // Handle form validation
    handleFormValidation();

    // Handle profile image change
    handleProfileImageChange();

    // Handle dynamic attributes in product form
    handleDynamicAttributes();
});

// Image preview in forms
function handleImagePreview() {
    const imageInput = document.getElementById('product-images');
    const previewContainer = document.getElementById('image-preview-container');
    
    if (imageInput && previewContainer) {
        imageInput.addEventListener('change', function(e) {
            previewContainer.innerHTML = '';
            const files = e.target.files;
            
            Array.from(files).forEach((file, index) => {
                if (file.type.startsWith('image/')) {
                    const reader = new FileReader();
                    
                    reader.onload = function(e) {
                        const div = document.createElement('div');
                        div.className = 'image-upload-preview';
                        div.innerHTML = `
                            <img src="${e.target.result}" alt="معاينة الصورة">
                            <button type="button" class="remove-image" data-index="${index}">
                                <i class="fas fa-times"></i>
                            </button>
                            <div class="form-check mt-2">
                                <input class="form-check-input" type="radio" name="primary_image" 
                                       value="${index}" ${index === 0 ? 'checked' : ''}>
                                <label class="form-check-label">صورة رئيسية</label>
                            </div>
                        `;
                        previewContainer.appendChild(div);
                    };
                    
                    reader.readAsDataURL(file);
                }
            });
        });
        
        // Handle remove image
        previewContainer.addEventListener('click', function(e) {
            if (e.target.closest('.remove-image')) {
                const index = e.target.closest('.remove-image').dataset.index;
                const dt = new DataTransfer();
                const files = imageInput.files;
                
                Array.from(files).forEach((file, i) => {
                    if (i != index) {
                        dt.items.add(file);
                    }
                });
                
                imageInput.files = dt.files;
                e.target.closest('.image-upload-preview').remove();
            }
        });
    }
}

// Handle favorite buttons
// Handle favorite buttons
function handleFavoriteButtons() {
    document.addEventListener('click', function(e) {
        if (e.target.closest('.favorite-btn')) {
            e.preventDefault();
            const btn = e.target.closest('.favorite-btn');
            const productId = btn.dataset.productId;
            
            fetch(`/products/api/favorite/${productId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    btn.classList.toggle('active');
                    const icon = btn.querySelector('i');
                    icon.classList.toggle('text-danger');
                    
                    // تحديث النص إذا كان الزر يحتوي على نص
                    if (btn.textContent.trim().length > 0) {
                        if (data.is_favorite) {
                            btn.innerHTML = '<i class="fas fa-heart text-danger me-2"></i>إزالة من المفضلة';
                        } else {
                            btn.innerHTML = '<i class="fas fa-heart me-2"></i>إضافة للمفضلة';
                        }
                    }
                } else if (data.message === 'يجب تسجيل الدخول لإضافة المنتج للمفضلة') {
                    window.location.href = '/auth/login?next=' + encodeURIComponent(window.location.pathname);
                }
            })
            .catch(error => console.error('Error:', error));
        }
    });
}

// Handle image gallery in product view
function handleImageGallery() {
    const mainImage = document.querySelector('.product-gallery .main-image img');
    const thumbnails = document.querySelectorAll('.product-gallery .thumbnail-images img');
    
    if (mainImage && thumbnails.length > 0) {
        thumbnails.forEach(thumbnail => {
            thumbnail.addEventListener('click', function() {
                mainImage.src = this.dataset.fullImage;
                thumbnails.forEach(t => t.classList.remove('active'));
                this.classList.add('active');
            });
        });
    }
}

// Handle chat functionality
function handleChat() {
    const chatForm = document.getElementById('chat-form');
    const chatMessages = document.getElementById('chat-messages');
    
    if (chatForm && chatMessages) {
        // Scroll to bottom of chat
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const messageInput = chatForm.querySelector('textarea');
            const message = messageInput.value.trim();
            
            if (message) {
                // Add message to chat immediately for better UX
                addMessageToChat(message, true);
                messageInput.value = '';
                
                // Send message to server
                fetch(chatForm.action, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ message: message })
                })
                .then(response => response.json())
                .then(data => {
                    if (!data.success) {
                        showToast('حدث خطأ في إرسال الرسالة', 'error');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showToast('حدث خطأ في إرسال الرسالة', 'error');
                });
            }
        });
    }
}

// Add message to chat
function addMessageToChat(message, isSent) {
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${isSent ? 'sent' : 'received'}`;
        messageDiv.textContent = message;
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// Handle search filters
function handleSearchFilters() {
    const sortBy = document.getElementById('sort-by');
    const sortDir = document.getElementById('sort-dir');
    
    if (sortBy && sortDir) {
        const applyFilters = () => {
            const form = document.getElementById('search-form');
            if (form) {
                form.submit();
            }
        };
        
        sortBy.addEventListener('change', applyFilters);
        sortDir.addEventListener('change', applyFilters);
    }
}

// Handle form validation
function handleFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            
            form.classList.add('was-validated');
        });
    });
}

// Handle profile image change
function handleProfileImageChange() {
    const profileImageInput = document.getElementById('profile-image-input');
    const profileImagePreview = document.getElementById('profile-image-preview');
    
    if (profileImageInput && profileImagePreview) {
        profileImageInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file && file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    profileImagePreview.src = e.target.result;
                };
                reader.readAsDataURL(file);
            }
        });
    }
}

// Handle dynamic attributes in product form
function handleDynamicAttributes() {
    const addAttributeBtn = document.getElementById('add-attribute-btn');
    const attributesContainer = document.getElementById('attributes-container');
    
    if (addAttributeBtn && attributesContainer) {
        let attributeIndex = 0;
        
        addAttributeBtn.addEventListener('click', function() {
            const attributeRow = document.createElement('div');
            attributeRow.className = 'row attribute-row mb-3';
            attributeRow.innerHTML = `
                <div class="col-md-4">
                    <input type="text" class="form-control" name="attributes[${attributeIndex}][name]" placeholder="اسم الخاصية">
                </div>
                <div class="col-md-7">
                    <input type="text" class="form-control" name="attributes[${attributeIndex}][value]" placeholder="قيمة الخاصية">
                </div>
                <div class="col-md-1">
                    <button type="button" class="btn btn-danger remove-attribute">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
            
            attributesContainer.appendChild(attributeRow);
            attributeIndex++;
        });
        
        // Handle remove attribute
        attributesContainer.addEventListener('click', function(e) {
            if (e.target.closest('.remove-attribute')) {
                e.target.closest('.attribute-row').remove();
            }
        });
    }
}

// Show toast notification
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.style.position = 'fixed';
        container.style.top = '20px';
        container.style.right = '20px';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${getToastClass(type)} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    document.getElementById('toast-container').appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
    });
}

// Get toast class based on type
function getToastClass(type) {
    switch (type) {
        case 'success':
            return 'success';
        case 'error':
            return 'danger';
        case 'warning':
            return 'warning';
        default:
            return 'primary';
    }
}

// Get CSRF token
function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

// Add CSRF token to all AJAX requests
$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
            xhr.setRequestHeader("X-CSRFToken", getCsrfToken());
        }
    }
});

// Smooth scroll to element
function smoothScrollTo(element) {
    if (element) {
        element.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }
}

// Format price with commas
function formatPrice(price) {
    return price.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Check if element is in viewport
function isInViewport(element) {
    const rect = element.getBoundingClientRect();
    return (
        rect.top >= 0 &&
        rect.left >= 0 &&
        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}