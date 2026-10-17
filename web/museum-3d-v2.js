/**
 * MuseumScene — Three.js 3D museum engine.
 * Renders 6 circular galleries around a central court,
 * loads corpus records as interactive 3D artifacts.
 */

class MuseumScene {
    constructor(canvasId) {
        this.canvasId = canvasId;
        this.canvas = null;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.api = null;
        this.artifacts = [];
        this.galleries = {};
        this.currentGallery = null;
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        this.keys = {};
        this.selectedArtifact = null;
    }

    /**
     * Initialize the 3D scene.
     */
    async init() {
        this.canvas = document.getElementById(this.canvasId);
        
        // Initialize API client
        this.api = new MuseumAPI();

        // Setup Three.js
        this._setupScene();
        this._setupCamera();
        this._setupRenderer();
        this._setupLighting();

        // Build the museum
        await this._buildMuseum();

        // Attach event listeners
        this._attachEventListeners();

        // Start animation loop
        this._animate();

        console.log('✓ Museum initialized');
    }

    /**
     * Setup the 3D scene.
     */
    _setupScene() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0a0e27);
        this.scene.fog = new THREE.Fog(0x0a0e27, 100, 150);
        this.scene.up.set(0, 1, 0);
    }

    /**
     * Setup the camera.
     */
    _setupCamera() {
        const width = window.innerWidth;
        const height = window.innerHeight;
        this.camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
        this.camera.position.set(0, 2, 0); // Start in central court
        this.camera.lookAt(0, 2, -5);
    }

    /**
     * Setup the WebGL renderer.
     */
    _setupRenderer() {
        this.renderer = new THREE.WebGLRenderer({ 
            canvas: this.canvas, 
            antialias: true, 
            alpha: true 
        });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFShadowShadowMap;
    }

    /**
     * Setup lighting.
     */
    _setupLighting() {
        // Ambient light
        const ambient = new THREE.AmbientLight(0xffffff, 0.5);
        this.scene.add(ambient);

        // Main directional light
        const directional = new THREE.DirectionalLight(0xffffff, 0.8);
        directional.position.set(20, 30, 20);
        directional.castShadow = true;
        directional.shadow.mapSize.width = 2048;
        directional.shadow.mapSize.height = 2048;
        directional.shadow.camera.left = -60;
        directional.shadow.camera.right = 60;
        directional.shadow.camera.top = 60;
        directional.shadow.camera.bottom = -60;
        this.scene.add(directional);
    }

    /**
     * Build the museum: central court + 6 galleries.
     */
    async _buildMuseum() {
        // Load gallery definitions from API
        const galleriesData = await this.api.getGalleries();

        // Create central court
        this._createCentralCourt();

        // Create each gallery
        for (const galleryDef of galleriesData.galleries) {
            await this._createGallery(galleryDef);
        }

        console.log(`✓ Built ${galleriesData.galleries.length} galleries`);
    }

    /**
     * Create the central court.
     */
    _createCentralCourt() {
        // Floor
        const floorGeom = new THREE.PlaneGeometry(50, 50);
        const floorMat = new THREE.MeshStandardMaterial({ 
            color: 0x1e293b,
            roughness: 0.8,
        });
        const floor = new THREE.Mesh(floorGeom, floorMat);
        floor.rotation.x = -Math.PI / 2;
        floor.receiveShadow = true;
        this.scene.add(floor);

        // Low bounding wall around court
        const wallGeom = new THREE.BoxGeometry(50, 0.5, 50);
        const wallMat = new THREE.MeshStandardMaterial({ 
            color: 0x0f172a,
            roughness: 0.9,
        });
        const wall = new THREE.Mesh(wallGeom, wallMat);
        wall.position.y = -0.25;
        wall.receiveShadow = true;
        this.scene.add(wall);
    }

    /**
     * Create a single gallery.
     */
    async _createGallery(galleryDef) {
        const galleryId = galleryDef.id;
        const pos = galleryDef.position;
        const color = new THREE.Color(galleryDef.theme_color);

        // Gallery floor (elevated platform)
        const floorGeom = new THREE.CircleGeometry(10, 32);
        const floorMat = new THREE.MeshStandardMaterial({
            color: color,
            metalness: 0.1,
            roughness: 0.7,
        });
        const floor = new THREE.Mesh(floorGeom, floorMat);
        floor.rotation.x = -Math.PI / 2;
        floor.position.set(pos.x, 0.05, pos.z);
        floor.receiveShadow = true;
        this.scene.add(floor);

        // Wall panel (for agent perspective display)
        const wallGeom = new THREE.PlaneGeometry(8, 4);
        const wallMat = new THREE.MeshStandardMaterial({
            color: new THREE.Color(0x1e293b),
            emissive: color,
            emissiveIntensity: 0.2,
            metalness: 0.2,
        });
        const wall = new THREE.Mesh(wallGeom, wallMat);
        wall.position.set(pos.x, 2, pos.z + 3);
        wall.castShadow = true;
        wall.receiveShadow = true;
        this.scene.add(wall);

        // Add gallery metadata to wall
        wall.userData = {
            galleryId: galleryId,
            galleryName: galleryDef.name,
            agent: galleryDef.agent,
        };

        // Accent light for this gallery
        const light = new THREE.PointLight(new THREE.Color(galleryDef.accent_color), 1, 30);
        light.position.set(pos.x, 5, pos.z);
        light.castShadow = true;
        this.scene.add(light);

        // Load exhibits for this gallery
        const exhibitsData = await this.api.getExhibits(galleryId, 1, 12);
        
        // Create artifact meshes (cubes) at niche positions
        const niches = galleryDef.niches || [];
        const exhibits = exhibitsData.exhibits || [];

        for (let i = 0; i < niches.length && i < exhibits.length; i++) {
            const niche = niches[i];
            const exhibit = exhibits[i];
            this._createArtifact(exhibit, niche.position, niche.size, color, galleryId);
        }

        // Store gallery metadata
        this.galleries[galleryId] = {
            name: galleryDef.name,
            agent: galleryDef.agent,
            position: pos,
            color: color,
            insights: exhibitsData.insights,
        };
    }

    /**
     * Create a single artifact mesh (cube/sphere).
     */
    _createArtifact(exhibit, position, size, galleryColor, galleryId) {
        // Create cube geometry
        const geom = new THREE.BoxGeometry(size, size, size);
        const mat = new THREE.MeshStandardMaterial({
            color: galleryColor,
            metalness: 0.4,
            roughness: 0.6,
            emissive: galleryColor,
            emissiveIntensity: 0.3,
        });
        const mesh = new THREE.Mesh(geom, mat);
        mesh.position.set(position.x, position.y, position.z);
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        // Store exhibit data on the mesh
        mesh.userData = {
            id: exhibit.id,
            title: exhibit.title,
            text: exhibit.text,
            source: exhibit.source,
            category: exhibit.category,
            date: exhibit.date,
            url: exhibit.url,
            image_url: exhibit.image_url,
            tags: exhibit.tags,
            galleryId: galleryId,
        };

        this.scene.add(mesh);
        this.artifacts.push(mesh);
    }

    /**
     * Attach event listeners.
     */
    _attachEventListeners() {
        // Window resize
        window.addEventListener('resize', () => this._onWindowResize());

        // Mouse movement for raycast
        document.addEventListener('mousemove', (e) => this._onMouseMove(e));

        // Click on artifacts
        document.addEventListener('click', (e) => {
            if (e.target.id === 'search-input' || e.target.closest('.sidebar-right')) {
                return;
            }
            this._onCanvasClick(e);
        });

        // Keyboard
        document.addEventListener('keydown', (e) => {
            this.keys[e.key.toLowerCase()] = true;
        });
        document.addEventListener('keyup', (e) => {
            this.keys[e.key.toLowerCase()] = false;
        });

        // UI buttons
        document.getElementById('btn-reset-view')?.addEventListener('click', () => {
            this.camera.position.set(0, 2, 0);
            this.camera.lookAt(0, 2, -5);
        });

        document.getElementById('btn-fullscreen')?.addEventListener('click', () => {
            this.canvas.requestFullscreen?.();
        });

        // Gallery list (sidebar)
        this._populateGalleryList();

        // Search
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.addEventListener('keyup', (e) => {
                if (e.key === 'Enter') {
                    this._performSearch(searchInput.value);
                }
            });
        }

        // Modal close
        document.getElementById('modal-close')?.addEventListener('click', () => {
            this._closeModal();
        });
        document.getElementById('modal-overlay')?.addEventListener('click', (e) => {
            if (e.target.id === 'modal-overlay') {
                this._closeModal();
            }
        });
    }

    /**
     * Populate gallery list in sidebar.
     */
    _populateGalleryList() {
        const list = document.getElementById('gallery-list');
        if (!list) return;

        list.innerHTML = '';
        for (const [galleryId, galleryData] of Object.entries(this.galleries)) {
            const item = document.createElement('div');
            item.className = 'gallery-item';
            item.textContent = galleryData.name;
            item.addEventListener('click', () => {
                this._navigateToGallery(galleryId);
            });
            list.appendChild(item);
        }
    }

    /**
     * Navigate camera to a gallery.
     */
    _navigateToGallery(galleryId) {
        const gallery = this.galleries[galleryId];
        if (!gallery) return;

        const pos = gallery.position;
        const targetX = pos.x;
        const targetY = 3;
        const targetZ = pos.z - 12;

        // Smooth camera animation
        const start = { x: this.camera.position.x, y: this.camera.position.y, z: this.camera.position.z };
        const duration = 1000;
        const startTime = Date.now();

        const animate = () => {
            const elapsed = Date.now() - startTime;
            const t = Math.min(elapsed / duration, 1);

            this.camera.position.x = start.x + (targetX - start.x) * t;
            this.camera.position.y = start.y + (targetY - start.y) * t;
            this.camera.position.z = start.z + (targetZ - start.z) * t;
            this.camera.lookAt(pos.x, 2, pos.z);

            if (t < 1) {
                requestAnimationFrame(animate);
            }
        };

        animate();
        this.currentGallery = galleryId;
        this._updateCurrentGalleryDisplay();
    }

    /**
     * Update current gallery display in sidebar.
     */
    _updateCurrentGalleryDisplay() {
        const display = document.getElementById('current-gallery');
        if (!display || !this.currentGallery) return;
        const gallery = this.galleries[this.currentGallery];
        display.textContent = gallery ? gallery.name : '—';
    }

    /**
     * Handle mouse movement (for highlighting artifacts on hover).
     */
    _onMouseMove(e) {
        this.mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
        this.mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
    }

    /**
     * Handle canvas click (artifact selection).
     */
    _onCanvasClick(e) {
        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.artifacts);

        if (intersects.length > 0) {
            const artifact = intersects[0].object;
            this._showArtifactModal(artifact.userData);
        }
    }

    /**
     * Show artifact detail modal.
     */
    _showArtifactModal(data) {
        const modal = document.getElementById('modal-overlay');
        if (!modal) return;

        document.getElementById('modal-title').textContent = data.title || 'Artifact';
        
        const metaHtml = [];
        if (data.source) metaHtml.push(`<div class="modal-meta-item">📚 ${data.source}</div>`);
        if (data.category) metaHtml.push(`<div class="modal-meta-item">🏷️ ${data.category}</div>`);
        if (data.date) metaHtml.push(`<div class="modal-meta-item">📅 ${data.date}</div>`);
        document.getElementById('modal-meta').innerHTML = metaHtml.join('');

        const imgEl = document.getElementById('modal-image');
        if (data.image_url) {
            imgEl.src = data.image_url;
            imgEl.style.display = 'block';
            imgEl.onerror = () => {
                imgEl.style.display = 'none';
            };
        } else {
            imgEl.style.display = 'none';
        }

        document.getElementById('modal-text').textContent = data.text || 'No description available.';

        const linkEl = document.getElementById('modal-link');
        if (data.url) {
            linkEl.href = data.url;
            linkEl.style.display = 'inline-block';
        } else {
            linkEl.style.display = 'none';
        }

        modal.classList.add('visible');
    }

    /**
     * Close artifact modal.
     */
    _closeModal() {
        const modal = document.getElementById('modal-overlay');
        if (modal) {
            modal.classList.remove('visible');
        }
    }

    /**
     * Perform search.
     */
    async _performSearch(query) {
        if (!query.trim()) return;

        const results = await this.api.search(query, null, 5);
        if (results.results && results.results.length > 0) {
            const firstResult = results.results[0];
            const galleryId = firstResult.gallery;
            this._navigateToGallery(galleryId);
            console.log(`Found ${results.total} results for "${query}"`);
        } else {
            console.log(`No results found for "${query}"`);
        }
    }

    /**
     * Handle window resize.
     */
    _onWindowResize() {
        const width = window.innerWidth;
        const height = window.innerHeight;
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    /**
     * Handle keyboard input for movement.
     */
    _handleMovement() {
        const speed = 0.15;
        const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(this.camera.quaternion);
        const right = new THREE.Vector3(1, 0, 0).applyQuaternion(this.camera.quaternion);

        if (this.keys['w']) {
            this.camera.position.addScaledVector(forward, speed);
        }
        if (this.keys['a']) {
            this.camera.position.addScaledVector(right, -speed);
        }
        if (this.keys['s']) {
            this.camera.position.addScaledVector(forward, -speed);
        }
        if (this.keys['d']) {
            this.camera.position.addScaledVector(right, speed);
        }
    }

    /**
     * Animation loop.
     */
    _animate() {
        requestAnimationFrame(() => this._animate());

        // Handle movement
        this._handleMovement();

        // Gentle artifact rotation
        const time = Date.now() * 0.0005;
        for (const artifact of this.artifacts) {
            artifact.rotation.x += 0.001;
            artifact.rotation.y += 0.002;
        }

        // Render
        this.renderer.render(this.scene, this.camera);
    }
}
