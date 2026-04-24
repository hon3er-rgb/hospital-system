class FastSpeedCore {
    constructor() {
        this.containerId = 'pjax-container';
        this.progressBar = null;
        this.cache = new Map(); // RAM Cache for 0ms access
        this.currentXHR = null;
        this.init();
    }

    init() {
        this.createProgressBar();

        // 1. Mouseover Preloading (The "Magic")
        document.addEventListener('mouseover', (e) => {
            const link = e.target.closest('a');
            if (this.isValidLink(link)) this.preload(link.href);
        });

        // 2. Mousedown Acceleration (Before "Click")
        document.addEventListener('mousedown', (e) => {
            const link = e.target.closest('a');
            if (this.isValidLink(link)) this.preload(link.href, 'high');
        });

        // 3. Smart Context-Aware Glow Effect (Dark Mode Only)
        document.addEventListener('mousemove', (e) => {
            if (document.documentElement.getAttribute('data-theme') === 'dark') {
                const bg = document.querySelector('.mesh-bg');
                if (bg) {
                    // 1. Update Position
                    bg.style.setProperty('--mouse-x', `${e.clientX}px`);
                    bg.style.setProperty('--mouse-y', `${e.clientY}px`);

                    // 2. Detect Color from Element under Mouse
                    let color = 'rgba(120, 119, 198, 0.05)'; // Default faint glow
                    const el = e.target.closest('[class*="tile-"], [class*="step-"], .btn-primary, .text-primary');

                    if (el) {
                        const cl = el.classList;
                        if (cl.contains('tile-blue') || cl.contains('step-accounting') || cl.contains('text-primary')) color = 'rgba(59, 130, 246, 0.15)'; // Blue
                        else if (cl.contains('tile-green') || cl.contains('step-pharmacy')) color = 'rgba(16, 185, 129, 0.15)'; // Green
                        else if (cl.contains('tile-red') || cl.contains('step-triage')) color = 'rgba(239, 68, 68, 0.15)'; // Red
                        else if (cl.contains('tile-indigo') || cl.contains('step-doctor')) color = 'rgba(99, 102, 241, 0.15)'; // Indigo
                        else if (cl.contains('tile-cyan') || cl.contains('step-tests')) color = 'rgba(6, 182, 212, 0.15)'; // Cyan
                        else if (cl.contains('tile-gray') || cl.contains('step-done')) color = 'rgba(148, 163, 184, 0.15)'; // Gray
                        else if (cl.contains('tile-warning')) color = 'rgba(245, 158, 11, 0.15)'; // Orange
                    }

                    bg.style.setProperty('--glow-color', color);
                }
            }
        });

        // 3. Click Handling
        document.addEventListener('click', (e) => this.handleClick(e));

        // 4. Back/Forward Handling
        window.addEventListener('popstate', (e) => this.handlePopState(e));

        console.log('🚀 Ultimate Speed Core v2.0 (Cached) Initialized');
    }

    createProgressBar() {
        this.progressBar = document.createElement('div');
        this.progressBar.id = 'fast-loader';
        Object.assign(this.progressBar.style, {
            position: 'fixed', top: '0', left: '0', height: '3px', width: '0%',
            backgroundColor: '#007bff', boxShadow: '0 0 15px #007bff',
            transition: 'width 0.05s linear', zIndex: '999999', pointerEvents: 'none'
        });
        document.body.appendChild(this.progressBar);
    }

    isValidLink(link) {
        return link && link.href.startsWith(window.location.origin) &&
            !link.hash && !link.target && !link.href.includes('#') &&
            !link.href.includes('javascript:') && !link.classList.contains('no-pjax');
    }

    async preload(url, priority = 'low') {
        if (this.cache.has(url)) return; // Already cached

        const controller = new AbortController();
        const signal = controller.signal;

        // Flag as pending
        this.cache.set(url, { status: 'pending', promise: null });

        const fetchPromise = fetch(url, { priority: priority, signal: signal })
            .then(res => res.text())
            .then(html => {
                const doc = new DOMParser().parseFromString(html, 'text/html');
                this.cache.set(url, { status: 'ready', content: doc, title: doc.title });
                return doc;
            })
            .catch(err => {
                this.cache.delete(url); // Retry later if failed
            });

        // Update cache record
        this.cache.set(url, { status: 'pending', promise: fetchPromise });
    }

    handleClick(e) {
        const link = e.target.closest('a');
        if (!this.isValidLink(link)) return;

        e.preventDefault();
        this.navigateTo(link.href);
    }

    handlePopState(e) {
        this.navigateTo(window.location.href, false);
    }

    async navigateTo(url, push = true) {
        this.progressBar.style.width = '60%';
        this.progressBar.style.opacity = '1';

        // Check Cache first
        let data = this.cache.get(url);

        if (!data) {
            // Not in cache? Fetch Now (with smart limit)
            if (this.cache.size > 20) { // Limit cache to 20 pages max
                this.cache.clear(); // Simple purge strategy for max speed
                console.log('🧹 Cache Purged for Speed');
            }
            this.preload(url, 'high');
            data = this.cache.get(url);
        }

        try {
            let doc;
            if (data.status === 'ready') {
                doc = data.content;
            } else if (data.status === 'pending') {
                doc = await data.promise;
            }

            if (!doc) throw new Error("Load failed");

            // RENDER - 0ms delay if cached
            this.render(doc);

            // Safety Cleanup: Remove any stuck modal backdrops from previous page
            document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
            document.body.classList.remove('modal-open');
            document.body.style.overflow = '';
            document.body.style.paddingRight = '';

            if (push) window.history.pushState({}, '', url);
            window.scrollTo(0, 0);

        } catch (error) {
            console.error(error);
            window.location.href = url;
        } finally {
            this.finishLoading();
        }
    }

    render(doc) {
        const newContainer = doc.getElementById(this.containerId);
        if (!newContainer) { window.location.reload(); return; }

        const currentContainer = document.getElementById(this.containerId);

        // Clean Exit
        currentContainer.classList.remove('animate-enter');

        // SWAP HARD
        currentContainer.innerHTML = newContainer.innerHTML;
        document.title = doc.title;

        // Animate Enter
        void currentContainer.offsetWidth;
        currentContainer.classList.add('animate-enter');

        // Execute Scripts
        this.executeScripts(currentContainer);

        // Trigger Event
        document.dispatchEvent(new Event('pjax:content-loaded'));
    }

    executeScripts(container) {
        container.querySelectorAll('script').forEach(oldScript => {
            const newScript = document.createElement('script');
            Array.from(oldScript.attributes).forEach(attr => newScript.setAttribute(attr.name, attr.value));
            newScript.textContent = oldScript.textContent;
            oldScript.parentNode.replaceChild(newScript, oldScript);
        });
    }

    finishLoading() {
        this.progressBar.style.width = '100%';
        setTimeout(() => {
            this.progressBar.style.opacity = '0';
            setTimeout(() => this.progressBar.style.width = '0%', 100);
        }, 100);
    }
}

// Auto Init
window.fastCore = new FastSpeedCore();
