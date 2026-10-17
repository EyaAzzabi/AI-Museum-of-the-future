/* ── AI Museum 3D Experience ─────────────────────────────────────────────── */

class MuseumScene {
    constructor() {
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.data = null;
        this.artifacts = [];
        this.rooms = [];
        this.lights = [];
        this.frameCount = 0;
        this.startTime = Date.now();
        this.init();
    }

    init() {
        this.setupScene();
        this.setupCamera();
        this.setupRenderer();
        this.setupLights();
        this.setupControls();
        this.createGallery();
        this.loadData();
        this.animate();
        window.addEventListener('resize', () => this.onWindowResize());
    }

    setupScene() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0a0e19);
        this.scene.fog = new THREE.Fog(0x0a0e19, 50, 300);
    }

    setupCamera() {
        const width = window.innerWidth;
        const height = window.innerHeight;
        this.camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
        this.camera.position.set(0, 1.6, 10);
        this.camera.lookAt(0, 1.6, 0);
    }

    setupRenderer() {
        const canvas = document.getElementById('three-canvas');
        this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFShadowShadowMap;
    }

    setupLights() {
        // Ambient light
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);
        this.lights.push(ambientLight);

        // Main directional light
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(20, 30, 20);
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 2048;
        directionalLight.shadow.mapSize.height = 2048;
        directionalLight.shadow.camera.left = -50;
        directionalLight.shadow.camera.right = 50;
        directionalLight.shadow.camera.top = 50;
        directionalLight.shadow.camera.bottom = -50;
        this.scene.add(directionalLight);
        this.lights.push(directionalLight);

        // Accent lights for atmosphere
        const accentLight1 = new THREE.PointLight(0x3b82f6, 0.5, 100);
        accentLight1.position.set(-30, 10, -30);
        this.scene.add(accentLight1);
        this.lights.push(accentLight1);

        const accentLight2 = new THREE.PointLight(0xa855f7, 0.4, 100);
        accentLight2.position.set(30, 10, -30);
        this.scene.add(accentLight2);
        this.lights.push(accentLight2);
    }

    setupControls() {
        // First-person camera controls
        this.keys = { w: false, a: false, s: false, d: false, space: false, ctrl: false };
        const moveSpeed = 0.15;
        const rotateSpeed = 0.003;

        document.addEventListener('keydown', (e) => {
            const key = e.key.toLowerCase();
            if (key === 'w') this.keys.w = true;
            if (key === 'a') this.keys.a = true;
            if (key === 's') this.keys.s = true;
            if (key === 'd') this.keys.d = true;
            if (key === ' ') { this.keys.space = true; e.preventDefault(); }
            if (key === 'control') this.keys.ctrl = true;
        });

        document.addEventListener('keyup', (e) => {
            const key = e.key.toLowerCase();
            if (key === 'w') this.keys.w = false;
            if (key === 'a') this.keys.a = false;
            if (key === 's') this.keys.s = false;
            if (key === 'd') this.keys.d = false;
            if (key === ' ') this.keys.space = false;
            if (key === 'control') this.keys.ctrl = false;
        });

        document.addEventListener('mousemove', (e) => {
            if (document.pointerLockElement) {
                const deltaX = e.movementX * rotateSpeed;
                const deltaY = e.movementY * rotateSpeed;

                const euler = new THREE.Euler(0, 0, 0, 'YXZ');
                euler.setFromQuaternion(this.camera.quaternion);
                euler.rotateY(-deltaX);
                euler.rotateX(-deltaY);
                euler.x = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, euler.x));
                this.camera.quaternion.setFromEuler(euler);
            }
        });

        document.addEventListener('click', () => {
            if (!document.pointerLockElement) {
                document.documentElement.requestPointerLock();
            }
        });

        document.addEventListener('pointerlockchange', () => {
            if (!document.pointerLockElement) {
                // Cursor released
            }
        });

        this.updateControls = () => {
            const forward = new THREE.Vector3();
            const right = new THREE.Vector3();
            this.camera.getWorldDirection(forward);
            forward.y = 0;
            forward.normalize();
            right.crossVectors(this.camera.up, forward).normalize();

            const velocity = new THREE.Vector3();
            if (this.keys.w) velocity.add(forward);
            if (this.keys.s) velocity.sub(forward);
            if (this.keys.d) velocity.add(right);
            if (this.keys.a) velocity.sub(right);
            if (this.keys.space) velocity.y += 1;
            if (this.keys.ctrl) velocity.y -= 1;

            if (velocity.length() > 0) {
                velocity.normalize().multiplyScalar(moveSpeed);
                this.camera.position.add(velocity);
            }
        };
    }

    createGallery() {
        // Floor
        const floorGeometry = new THREE.PlaneGeometry(100, 100);
        const floorMaterial = new THREE.MeshStandardMaterial({
            color: 0x1a2235,
            roughness: 0.8,
            metalness: 0.1,
        });
        const floor = new THREE.Mesh(floorGeometry, floorMaterial);
        floor.rotation.x = -Math.PI / 2;
        floor.receiveShadow = true;
        this.scene.add(floor);

        // Walls
        this.createWalls();

        // Central display pedestal
        this.createPedestal();

        // Display panels on walls
        this.createDisplayPanels();
    }

    createWalls() {
        const wallMaterial = new THREE.MeshStandardMaterial({
            color: 0x111827,
            roughness: 0.9,
            metalness: 0.0,
        });

        // Back wall
        const backWall = new THREE.Mesh(new THREE.BoxGeometry(100, 40, 2), wallMaterial);
        backWall.position.z = -50;
        backWall.position.y = 20;
        backWall.castShadow = true;
        backWall.receiveShadow = true;
        this.scene.add(backWall);

        // Front wall
        const frontWall = new THREE.Mesh(new THREE.BoxGeometry(100, 40, 2), wallMaterial);
        frontWall.position.z = 50;
        frontWall.position.y = 20;
        frontWall.castShadow = true;
        frontWall.receiveShadow = true;
        this.scene.add(frontWall);

        // Left wall
        const leftWall = new THREE.Mesh(new THREE.BoxGeometry(2, 40, 100), wallMaterial);
        leftWall.position.x = -50;
        leftWall.position.y = 20;
        leftWall.castShadow = true;
        leftWall.receiveShadow = true;
        this.scene.add(leftWall);

        // Right wall
        const rightWall = new THREE.Mesh(new THREE.BoxGeometry(2, 40, 100), wallMaterial);
        rightWall.position.x = 50;
        rightWall.position.y = 20;
        rightWall.castShadow = true;
        rightWall.receiveShadow = true;
        this.scene.add(rightWall);

        // Ceiling
        const ceiling = new THREE.Mesh(new THREE.PlaneGeometry(100, 100), wallMaterial);
        ceiling.rotation.x = Math.PI / 2;
        ceiling.position.y = 40;
        ceiling.receiveShadow = true;
        this.scene.add(ceiling);
    }

    createPedestal() {
        const pedestalGeometry = new THREE.CylinderGeometry(8, 10, 2, 32);
        const pedestalMaterial = new THREE.MeshStandardMaterial({
            color: 0x1e293b,
            roughness: 0.4,
            metalness: 0.3,
        });
        const pedestal = new THREE.Mesh(pedestalGeometry, pedestalMaterial);
        pedestal.position.y = 1;
        pedestal.castShadow = true;
        pedestal.receiveShadow = true;
        this.scene.add(pedestal);

        // Floating artifact display
        const displayGeometry = new THREE.TorusGeometry(6, 0.3, 16, 16);
        const displayMaterial = new THREE.MeshStandardMaterial({
            color: 0x3b82f6,
            emissive: 0x3b82f6,
            emissiveIntensity: 0.3,
            metalness: 0.8,
            roughness: 0.2,
        });
        const display = new THREE.Mesh(displayGeometry, displayMaterial);
        display.position.y = 4;
        display.rotation.x = Math.PI / 2.5;
        display.castShadow = true;
        this.scene.add(display);

        // Rotating animation
        this.displayRing = display;
    }

    createDisplayPanels() {
        const panelPositions = [
            { x: -30, z: -40, rotation: 0 },
            { x: 30, z: -40, rotation: 0 },
            { x: -40, z: 0, rotation: Math.PI / 2 },
            { x: 40, z: 0, rotation: -Math.PI / 2 },
            { x: -30, z: 40, rotation: Math.PI },
            { x: 30, z: 40, rotation: Math.PI },
        ];

        const panelMaterial = new THREE.MeshStandardMaterial({
            color: 0x0f172a,
            metalness: 0.2,
            roughness: 0.5,
            emissive: 0x1e3a8a,
            emissiveIntensity: 0.1,
        });

        panelPositions.forEach((pos, idx) => {
            const panelGroup = new THREE.Group();
            
            // Panel background
            const panelGeometry = new THREE.PlaneGeometry(16, 24);
            const panel = new THREE.Mesh(panelGeometry, panelMaterial);
            panel.castShadow = true;
            panel.receiveShadow = true;
            panelGroup.add(panel);

            // Frame
            const frameGeometry = new THREE.EdgesGeometry(panelGeometry);
            const frameLines = new THREE.LineSegments(frameGeometry, new THREE.LineBasicMaterial({ color: 0x3b82f6, linewidth: 2 }));
            panelGroup.add(frameLines);

            // Label
            const canvas = document.createElement('canvas');
            canvas.width = 512;
            canvas.height = 768;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#0f172a';
            ctx.fillRect(0, 0, 512, 768);
            ctx.fillStyle = '#3b82f6';
            ctx.font = 'bold 32px Arial';
            ctx.textAlign = 'center';
            ctx.fillText(`GALLERY ${idx + 1}`, 256, 80);
            ctx.font = '16px Arial';
            ctx.fillStyle = '#94a3b8';
            const labels = ['Historians', 'Sociologists', 'Technologists', 'Cultural', 'Visual', 'Curator'];
            ctx.fillText(labels[idx] || 'Gallery', 256, 150);

            const texture = new THREE.CanvasTexture(canvas);
            const textMaterial = new THREE.MeshBasicMaterial({ map: texture });
            const textGeometry = new THREE.PlaneGeometry(15.8, 23.8);
            const textMesh = new THREE.Mesh(textGeometry, textMaterial);
            textMesh.position.z = 0.01;
            panelGroup.add(textMesh);

            panelGroup.position.set(pos.x, 12, pos.z);
            panelGroup.rotation.y = pos.rotation;
            this.scene.add(panelGroup);
            this.rooms.push(panelGroup);
        });
    }

    async loadData() {
        try {
            const response = await fetch('/api/validate');
            const data = await response.json();
            this.data = data;

            // Update stats
            document.getElementById('stat-rooms').textContent = this.rooms.length;
            document.getElementById('stat-objects').textContent = data.corpus_files?.length || 0;
            document.getElementById('stat-points').textContent = (data.corpus_files || []).reduce((sum, f) => sum + (f.records || 0), 0);
            document.getElementById('stat-camera').textContent = 'First Person';
            document.getElementById('stat-lights').textContent = this.lights.length;
            document.getElementById('data-status').textContent = '✓ Loaded';

            // Update HUD info
            const info = document.getElementById('hud-info');
            info.innerHTML = `
                <div class="hud-info-title">Exhibition Status</div>
                <div class="hud-info-text">
                    ${data.summary || 'Pipeline validation complete'}<br>
                    <strong>${data.steps?.filter(s => s.ok).length || 0}/${data.steps?.length || 0}</strong> steps validated
                </div>
            `;

            // Create artifact cubes based on corpus data
            this.createArtifactCubes();
        } catch (error) {
            console.error('Error loading data:', error);
            document.getElementById('data-status').textContent = '✗ Error';
        }
    }

    createArtifactCubes() {
        if (!this.data?.corpus_files) return;

        const files = this.data.corpus_files;
        const count = Math.min(files.length, 20);

        for (let i = 0; i < count; i++) {
            const file = files[i];
            const geometry = new THREE.BoxGeometry(1, 1, 1);
            const hue = (i / count) * 0.6;
            const color = new THREE.Color().setHSL(hue, 0.7, 0.5);
            const material = new THREE.MeshStandardMaterial({
                color: color,
                emissive: color,
                emissiveIntensity: 0.3,
                metalness: 0.6,
                roughness: 0.3,
            });
            const cube = new THREE.Mesh(geometry, material);

            // Random position around center
            const angle = (i / count) * Math.PI * 2;
            const radius = 15 + Math.sin(i) * 8;
            cube.position.set(
                Math.cos(angle) * radius,
                3 + Math.sin(i * 0.5) * 2,
                Math.sin(angle) * radius
            );

            cube.castShadow = true;
            cube.receiveShadow = true;
            cube.userData.label = file.name;
            cube.userData.records = file.records;

            this.artifacts.push(cube);
            this.scene.add(cube);
        }
    }

    updateUI() {
        // Update FPS
        this.frameCount++;
        const elapsed = Date.now() - this.startTime;
        if (elapsed > 1000) {
            const fps = Math.round((this.frameCount * 1000) / elapsed);
            document.getElementById('fps-badge').textContent = `${fps} FPS`;
            this.frameCount = 0;
            this.startTime = Date.now();
        }
    }

    animate = () => {
        requestAnimationFrame(this.animate);

        // Update controls
        this.updateControls();

        // Animate display ring
        if (this.displayRing) {
            this.displayRing.rotation.x += 0.003;
            this.displayRing.rotation.z += 0.002;
        }

        // Animate artifacts
        this.artifacts.forEach((artifact, idx) => {
            artifact.rotation.x += 0.005 + idx * 0.001;
            artifact.rotation.y += 0.008 + idx * 0.002;
            artifact.position.y += Math.sin(Date.now() * 0.0005 + idx) * 0.005;
        });

        // Update UI
        this.updateUI();

        // Render
        this.renderer.render(this.scene, this.camera);
    };

    onWindowResize() {
        const width = window.innerWidth;
        const height = window.innerHeight;
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    const museum = new MuseumScene();

    // Button handlers
    document.getElementById('btn-validate').addEventListener('click', () => {
        window.open('/', '_blank');
    });

    document.getElementById('btn-fullscreen').addEventListener('click', () => {
        document.documentElement.requestFullscreen().catch(e => console.log('Fullscreen failed:', e));
    });

    document.getElementById('panel-close').addEventListener('click', () => {
        const panel = document.querySelector('.panel-right');
        panel.style.display = panel.style.display === 'none' ? 'flex' : 'none';
    });
});
