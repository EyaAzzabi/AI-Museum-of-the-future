import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

export default function MuseumScene3D({ onSelectArtifact, featuredItems = [] }) {
  const mountRef = useRef(null);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth;
    const height = container.clientHeight;

    // 1. Scene, Camera, Renderer
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x060818);
    scene.fog = new THREE.FogExp2(0x060818, 0.025);

    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
    camera.position.set(0, 2.5, 12);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);

    // 2. Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const pointLight = new THREE.PointLight(0x6366f1, 2.5, 30);
    pointLight.position.set(0, 6, 0);
    scene.add(pointLight);

    // Floor Grid
    const gridHelper = new THREE.GridHelper(50, 40, 0x3b82f6, 0x1e293b);
    gridHelper.position.y = -0.01;
    scene.add(gridHelper);

    // Circular Exhibition Pedestals
    const interactiveMeshes = [];
    const radius = 6.5;
    const items = featuredItems.length > 0 ? featuredItems.slice(0, 6) : [
      { id: '1', title: 'Intelligence Artificielle Raisonnante', category: 'technology' },
      { id: '2', title: 'Archives Numériques Citoyennes', category: 'sociologist' },
      { id: '3', title: 'Cinéma & Identité Maghrébine', category: 'culture_art' },
      { id: '4', title: 'Traités Climatiques Transméditerranéens', category: 'historian' },
      { id: '5', title: 'Restitution Photographique 3D', category: 'visual' },
      { id: '6', title: 'Synthèse Curateur 2026', category: 'curator' },
    ];

    const group = new THREE.Group();
    scene.add(group);

    items.forEach((item, index) => {
      const angle = (index / items.length) * Math.PI * 2;
      const x = Math.cos(angle) * radius;
      const z = Math.sin(angle) * radius;

      // Base Pedestal
      const pedestalGeo = new THREE.CylinderGeometry(0.7, 0.85, 0.8, 24);
      const pedestalMat = new THREE.MeshStandardMaterial({
        color: 0x111827,
        roughness: 0.3,
        metalness: 0.8,
      });
      const pedestal = new THREE.Mesh(pedestalGeo, pedestalMat);
      pedestal.position.set(x, 0.4, z);
      group.add(pedestal);

      // Holographic Floating Artifact Slab
      const slabGeo = new THREE.BoxGeometry(0.9, 1.4, 0.1);
      const slabMat = new THREE.MeshStandardMaterial({
        color: 0x38bdf8,
        emissive: 0x0284c7,
        emissiveIntensity: 0.4,
        roughness: 0.1,
        metalness: 0.9,
        transparent: true,
        opacity: 0.85,
      });
      const slab = new THREE.Mesh(slabGeo, slabMat);
      slab.position.set(x, 1.6, z);
      slab.rotation.y = -angle - Math.PI / 2;
      slab.userData = item;
      group.add(slab);
      interactiveMeshes.push(slab);
    });

    // Central Pillar / Beacon
    const beaconGeo = new THREE.CylinderGeometry(0.3, 0.3, 6, 32);
    const beaconMat = new THREE.MeshStandardMaterial({
      color: 0x6366f1,
      emissive: 0x4f46e5,
      emissiveIntensity: 0.8,
      transparent: true,
      opacity: 0.7,
    });
    const beacon = new THREE.Mesh(beaconGeo, beaconMat);
    beacon.position.set(0, 3, 0);
    scene.add(beacon);

    // Mouse Interaction / Raycasting
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const handlePointerMove = (e) => {
      const rect = container.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / container.clientWidth) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / container.clientHeight) * 2 + 1;
    };

    const handleClick = () => {
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(interactiveMeshes);
      if (intersects.length > 0) {
        const selected = intersects[0].object.userData;
        if (onSelectArtifact) onSelectArtifact(selected);
      }
    };

    container.addEventListener('pointermove', handlePointerMove);
    container.addEventListener('click', handleClick);

    // Resize
    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    // Animation Loop
    let animationFrameId;
    let clock = new THREE.Clock();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const elapsedTime = clock.getElapsedTime();

      // Gentle auto-rotation
      group.rotation.y = elapsedTime * 0.08;

      // Slight bobbing on slabs
      interactiveMeshes.forEach((mesh, i) => {
        mesh.position.y = 1.6 + Math.sin(elapsedTime * 2 + i) * 0.08;
      });

      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
      container.removeEventListener('pointermove', handlePointerMove);
      container.removeEventListener('click', handleClick);
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, [featuredItems, onSelectArtifact]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: '480px' }}>
      <div ref={mountRef} style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }} />
      <div style={{
        position: 'absolute',
        bottom: '16px',
        left: '50%',
        transform: 'translateX(-50%)',
        background: 'rgba(10, 14, 39, 0.75)',
        backdropFilter: 'blur(8px)',
        padding: '8px 18px',
        borderRadius: '20px',
        border: '1px solid rgba(148, 163, 184, 0.2)',
        fontSize: '12px',
        color: '#94a3b8',
        pointerEvents: 'none'
      }}>
        ✨ Cliquez sur une stèle holographique pour ouvrir la fiche détaillée de l'objet
      </div>
    </div>
  );
}
