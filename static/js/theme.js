// static/js/theme.js - Enhanced Theme Toggle Functionality
class ThemeManager {
    constructor() {
        this.themes = ['light', 'dark', 'neon'];
        this.currentTheme = this.getStoredTheme() || this.getSystemTheme();
        this.init();
    }

    init() {
        this.applyTheme(this.currentTheme);
        this.setupEventListeners();
        this.updateToggleIcon();
        this.addThemeChangeObservers();
        this.enhanceTextVisibility();
    }

    getStoredTheme() {
        return localStorage.getItem('theme');
    }

    getSystemTheme() {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        return 'light';
    }

    setStoredTheme(theme) {
        localStorage.setItem('theme', theme);
    }

    applyTheme(theme) {
        // Remove all theme classes first
        document.documentElement.classList.remove('theme-light', 'theme-dark', 'theme-neon');
        
        // Set the data attribute and class
        document.documentElement.setAttribute('data-theme', theme);
        document.documentElement.classList.add(`theme-${theme}`);
        
        this.currentTheme = theme;
        this.setStoredTheme(theme);
        this.updateToggleIcon();
        this.dispatchThemeChangeEvent();
        this.updateMetaThemeColor();
        this.enhanceTextVisibility();
        
        // Add smooth transition
        document.body.style.transition = 'background-color 0.3s ease, color 0.3s ease';
    }

    enhanceTextVisibility() {
        // Enhanced text visibility for all themes
        const textElements = document.querySelectorAll('h1, h2, h3, h4, h5, h6, .card-title, .card-header, .navbar-brand');
        
        textElements.forEach(el => {
            if (!el.classList.contains('theme-text-enhanced')) {
                el.classList.add('theme-text-enhanced', 'enhanced-text');
            }
        });

        // Add specific shadow classes based on theme
        const shadowClass = this.currentTheme === 'light' ? 'text-shadow' : 
                           this.currentTheme === 'dark' ? 'text-shadow-dark' : 'text-shadow-glow';
        
        textElements.forEach(el => {
            el.classList.add(shadowClass);
        });
    }

    updateMetaThemeColor() {
        let metaThemeColor = document.querySelector("meta[name=theme-color]");
        if (!metaThemeColor) {
            metaThemeColor = document.createElement('meta');
            metaThemeColor.name = 'theme-color';
            document.head.appendChild(metaThemeColor);
        }

        switch (this.currentTheme) {
            case 'dark':
                metaThemeColor.content = '#0F0F1B';
                break;
            case 'neon':
                metaThemeColor.content = '#0A0A14';
                break;
            case 'light':
            default:
                metaThemeColor.content = '#4B33FF';
                break;
        }
    }

    setupEventListeners() {
        const toggleBtn = document.getElementById('theme-toggle');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => this.toggleTheme());
            toggleBtn.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.toggleTheme();
                }
            });
        }

        // Listen for system theme changes
        if (window.matchMedia) {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            mediaQuery.addEventListener('change', (e) => {
                if (!this.getStoredTheme()) {
                    this.applyTheme(e.matches ? 'dark' : 'light');
                }
            });
        }

        // Add keyboard shortcut (Alt+T)
        document.addEventListener('keydown', (e) => {
            if (e.altKey && e.key === 't') {
                e.preventDefault();
                this.toggleTheme();
            }
        });
    }

    addThemeChangeObservers() {
        // Observe DOM changes to ensure new elements get proper theme styling
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList') {
                    this.ensureThemeConsistency();
                    this.enhanceTextVisibility();
                }
            });
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    ensureThemeConsistency() {
        // Ensure all interactive elements have proper theme classes
        const elements = document.querySelectorAll('.card, .btn, .form-control, .dropdown-menu');
        elements.forEach(element => {
            if (!element.classList.contains('theme-aware')) {
                element.classList.add('theme-aware');
            }
        });
    }

    toggleTheme() {
        const currentIndex = this.themes.indexOf(this.currentTheme);
        const nextIndex = (currentIndex + 1) % this.themes.length;
        const nextTheme = this.themes[nextIndex];
        this.applyTheme(nextTheme);
        
        // Add animation feedback
        const toggleBtn = document.getElementById('theme-toggle');
        if (toggleBtn) {
            toggleBtn.style.transform = 'scale(0.8)';
            setTimeout(() => {
                toggleBtn.style.transform = 'scale(1)';
            }, 150);
        }

        // Show theme change notification
        this.showThemeNotification(nextTheme);
    }

    showThemeNotification(theme) {
        // Remove existing notification
        const existingNotification = document.getElementById('theme-notification');
        if (existingNotification) {
            existingNotification.remove();
        }

        const notification = document.createElement('div');
        notification.id = 'theme-notification';
        notification.className = 'theme-notification fade-in';
        notification.innerHTML = `
            <div class="glass-card p-3">
                <i class="fas fa-palette me-2"></i>
                Theme changed to <strong>${theme.charAt(0).toUpperCase() + theme.slice(1)}</strong>
            </div>
        `;

        // Add styles for notification
        if (!document.getElementById('theme-notification-styles')) {
            const styles = document.createElement('style');
            styles.id = 'theme-notification-styles';
            styles.textContent = `
                .theme-notification {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 10000;
                    animation: slideInRight 0.3s ease-out;
                }
                @keyframes slideInRight {
                    from {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
            `;
            document.head.appendChild(styles);
        }

        document.body.appendChild(notification);

        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.animation = 'slideOutRight 0.3s ease-in';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.remove();
                    }
                }, 300);
            }
        }, 3000);
    }

    updateToggleIcon() {
        const toggleBtn = document.getElementById('theme-toggle');
        if (!toggleBtn) return;

        const icon = toggleBtn.querySelector('i');
        if (!icon) return;

        // Remove all icon classes
        icon.className = 'fas';

        // Add appropriate icon based on theme
        switch (this.currentTheme) {
            case 'dark':
                icon.classList.add('fa-moon');
                toggleBtn.setAttribute('aria-label', 'Switch to Neon theme');
                toggleBtn.title = 'Switch to Neon theme';
                break;
            case 'neon':
                icon.classList.add('fa-palette');
                toggleBtn.setAttribute('aria-label', 'Switch to Light theme');
                toggleBtn.title = 'Switch to Light theme';
                break;
            case 'light':
            default:
                icon.classList.add('fa-sun');
                toggleBtn.setAttribute('aria-label', 'Switch to Dark theme');
                toggleBtn.title = 'Switch to Dark theme';
                break;
        }
    }

    getNextTheme() {
        const currentIndex = this.themes.indexOf(this.currentTheme);
        const nextIndex = (currentIndex + 1) % this.themes.length;
        return this.themes[nextIndex];
    }

    dispatchThemeChangeEvent() {
        const event = new CustomEvent('themeChange', {
            detail: { 
                theme: this.currentTheme,
                nextTheme: this.getNextTheme()
            }
        });
        document.dispatchEvent(event);
    }

    // Public method to get current theme
    getCurrentTheme() {
        return this.currentTheme;
    }

    // Public method to set specific theme
    setTheme(theme) {
        if (this.themes.includes(theme)) {
            this.applyTheme(theme);
        }
    }
}

// Initialize theme manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();
    
    // Add theme class to body for additional styling control
    document.body.classList.add('theme-loaded');
    
    // Enhanced text visibility initialization
    setTimeout(() => {
        window.themeManager.enhanceTextVisibility();
    }, 100);
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ThemeManager;
}