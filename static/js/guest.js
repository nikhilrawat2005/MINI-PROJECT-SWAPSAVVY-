// static/js/guest.js - Guest UI Management
class GuestManager {
    constructor() {
        this.isGuest = document.body.classList.contains('guest-user');
        this.init();
    }

    init() {
        if (this.isGuest) {
            this.protectInteractiveElements();
            this.setupGuestModals();
            this.setupSessionTimer();
        }
    }

    protectInteractiveElements() {
        // Add guest protection to all interactive elements
        const protectedSelectors = [
            '.like-btn',
            '.follow-btn',
            '.connect-btn',
            '[data-guest-protected]',
            'form:not([action*="search"])',
            '.btn-primary:not([href*="signup"]):not([href*="login"]):not([href*="upgrade"])'
        ];

        protectedSelectors.forEach(selector => {
            document.querySelectorAll(selector).forEach(element => {
                if (!element.hasAttribute('data-guest-handled')) {
                    element.setAttribute('data-guest-handled', 'true');
                    element.addEventListener('click', this.handleGuestAction.bind(this));
                }
            });
        });
    }

    handleGuestAction(event) {
        event.preventDefault();
        event.stopPropagation();

        const element = event.target.closest('[data-guest-protected], .like-btn, .follow-btn, .connect-btn, form, .btn-primary');
        
        if (element && this.shouldProtectElement(element)) {
            this.showGuestModal();
        }
    }

    shouldProtectElement(element) {
        // Allow navigation and search elements
        const allowedHrefs = ['/search', '/explore', '/profile', '/browse-as-guest', '/upgrade-from-guest', '/signup', '/login'];
        if (element.href) {
            return !allowedHrefs.some(allowed => element.href.includes(allowed));
        }
        return true;
    }

    showGuestModal() {
        const modal = new bootstrap.Modal(document.getElementById('guestModal'));
        modal.show();
    }

    setupGuestModals() {
        // Ensure guest modal exists
        if (!document.getElementById('guestModal')) {
            this.createGuestModal();
        }
    }

    createGuestModal() {
        const modalHTML = `
            <div class="modal fade" id="guestModal" tabindex="-1" aria-labelledby="guestModalLabel" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="guestModalLabel">
                                <i class="fas fa-user-lock me-2"></i>Guest Access Limited
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <p>You're currently browsing as a guest. To access this feature:</p>
                            <ul>
                                <li>Create a free account</li>
                                <li>Connect with professionals</li>
                                <li>Share your own content</li>
                                <li>Access all platform features</li>
                            </ul>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Continue Browsing</button>
                            <a href="/upgrade-from-guest" class="btn btn-primary">
                                <i class="fas fa-user-plus me-2"></i>Create Account
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }

    setupSessionTimer() {
        // Show session expiry warning 1 hour before expiry
        const expiryTime = sessionStorage.getItem('guest_expiry');
        if (expiryTime) {
            const expiryDate = new Date(expiryTime);
            const warningTime = new Date(expiryDate.getTime() - 60 * 60 * 1000); // 1 hour before
            
            const now = new Date();
            if (now >= warningTime) {
                this.showExpiryWarning(expiryDate);
            } else {
                setTimeout(() => {
                    this.showExpiryWarning(expiryDate);
                }, warningTime - now);
            }
        }
    }

    showExpiryWarning(expiryDate) {
        const timeLeft = Math.max(0, expiryDate - new Date());
        const hoursLeft = Math.floor(timeLeft / (1000 * 60 * 60));
        
        if (hoursLeft <= 1) {
            const alertHTML = `
                <div class="alert alert-warning alert-dismissible fade show" role="alert">
                    <i class="fas fa-clock me-2"></i>
                    Your guest session expires in ${hoursLeft} hour${hoursLeft !== 1 ? 's' : ''}. 
                    <a href="/upgrade-from-guest" class="alert-link">Create an account</a> to save your preferences.
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `;
            
            const existingAlert = document.querySelector('.alert-warning');
            if (!existingAlert) {
                document.querySelector('.container-fluid').insertAdjacentHTML('afterbegin', alertHTML);
            }
        }
    }

    // API call interceptor for guest protection
    static interceptApiCalls() {
        const originalFetch = window.fetch;
        window.fetch = function(...args) {
            const url = args[0];
            const options = args[1] || {};
            
            // Check if this is a protected API call
            if (GuestManager.isProtectedApiCall(url, options.method)) {
                return Promise.resolve({
                    ok: false,
                    status: 403,
                    json: () => Promise.resolve({
                        error: 'guest_read_only',
                        message: 'Please create an account to perform this action'
                    })
                });
            }
            
            return originalFetch.apply(this, args);
        };
    }

    static isProtectedApiCall(url, method) {
        if (typeof url === 'string') {
            const protectedEndpoints = [
                '/post/', '/like', '/follow', '/comment', '/message',
                '/notifications', '/profile/edit', '/connections'
            ];
            
            const isProtected = protectedEndpoints.some(endpoint => url.includes(endpoint));
            const isWriteMethod = ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method?.toUpperCase());
            
            return isProtected && isWriteMethod;
        }
        return false;
    }
}

// Initialize guest manager when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    new GuestManager();
    
    // Intercept API calls for guest protection
    if (document.body.classList.contains('guest-user')) {
        GuestManager.interceptApiCalls();
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GuestManager;
}