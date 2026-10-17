import React, { useState, useEffect } from 'react';
import { 
  fetchMuseumMeta, 
  fetchTimelineEvents, 
  fetchExhibits 
} from './services/api';

import MuseumScene3D from './components/MuseumScene3D';
import ArtifactDetailModal from './components/ArtifactDetailModal';
import GuideChatModal from './components/GuideChatModal';
import MuseumPlanView from './components/MuseumPlanView';
import TimelineView from './components/TimelineView';

import { 
  Compass, 
  Map, 
  Clock, 
  MessageSquare, 
  Sparkles, 
  ArrowRight, 
  Home, 
  Globe 
} from 'lucide-react';

export default function App() {
  // Navigation: 'home' | 'plan' | 'museum3d' | 'timeline'
  const [currentView, setCurrentView] = useState('home');
  const [exhibitionData, setExhibitionData] = useState(null);
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [selectedArtifact, setSelectedArtifact] = useState(null);
  const [isGuideOpen, setIsGuideOpen] = useState(false);
  const [guideInitialContext, setGuideInitialContext] = useState(null);
  const [timelineEvents, setTimelineEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [meta, timeline] = await Promise.all([
          fetchMuseumMeta(),
          fetchTimelineEvents()
        ]);
        setExhibitionData(meta);
        setTimelineEvents(timeline.events || []);
        if (meta.rooms && meta.rooms.length > 0) {
          setSelectedRoom(meta.rooms[0]);
        }
      } catch (err) {
        console.error('Data loading error:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const handleOpenArtifactFrom3D = (item) => {
    setSelectedArtifact(item);
  };

  const handleAskGuideFromArtifact = (item) => {
    setSelectedArtifact(null);
    setGuideInitialContext(item);
    setIsGuideOpen(true);
  };

  const handleEnter3D = (room) => {
    setSelectedRoom(room);
    setCurrentView('museum3d');
  };

  if (loading) {
    return (
      <div style={{
        width: '100vw',
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-deep)',
        color: '#94a3b8'
      }}>
        <div style={{
          width: '50px',
          height: '50px',
          borderRadius: '50%',
          border: '3px solid rgba(99, 102, 241, 0.2)',
          borderTopColor: '#6366f1',
          animation: 'spin 1s linear infinite'
        }} />
        <p style={{ marginTop: '20px', fontSize: '14px', letterSpacing: '0.05em' }}>
          CHARGEMENT DE L'EXPOSITION 2026 → 2126...
        </p>
        <style>{`@keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* ── Top Navigation Bar ────────────────────────────────────────── */}
      <header style={{
        position: 'sticky',
        top: 0,
        zIndex: 500,
        backgroundColor: 'rgba(5, 7, 20, 0.85)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid var(--border-subtle)',
        padding: '14px 32px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        {/* Brand */}
        <div 
          onClick={() => setCurrentView('home')} 
          style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}
        >
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            background: 'radial-gradient(circle, #f59e0b 0%, #b45309 100%)',
            boxShadow: '0 0 14px rgba(245, 158, 11, 0.45)'
          }} />
          <span style={{ fontSize: '18px', fontWeight: 800, letterSpacing: '-0.02em', color: '#f8fafc' }}>
            AI Museum of the Future
          </span>
        </div>

        {/* Nav Links */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => setCurrentView('home')}
            style={{
              background: currentView === 'home' ? 'rgba(255,255,255,0.08)' : 'transparent',
              color: currentView === 'home' ? '#f8fafc' : '#94a3b8',
              border: 'none',
              padding: '8px 14px',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Home size={15} /> Accueil
          </button>

          <button
            onClick={() => setCurrentView('plan')}
            style={{
              background: currentView === 'plan' ? 'rgba(255,255,255,0.08)' : 'transparent',
              color: currentView === 'plan' ? '#f8fafc' : '#94a3b8',
              border: 'none',
              padding: '8px 14px',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Map size={15} /> Plan du musée
          </button>

          <button
            onClick={() => setCurrentView('museum3d')}
            style={{
              background: currentView === 'museum3d' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
              color: currentView === 'museum3d' ? '#a5b4fc' : '#94a3b8',
              border: `1px solid ${currentView === 'museum3d' ? 'rgba(99, 102, 241, 0.4)' : 'transparent'}`,
              padding: '8px 14px',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Compass size={15} /> Vue 3D
          </button>

          <button
            onClick={() => setCurrentView('timeline')}
            style={{
              background: currentView === 'timeline' ? 'rgba(255,255,255,0.08)' : 'transparent',
              color: currentView === 'timeline' ? '#f8fafc' : '#94a3b8',
              border: 'none',
              padding: '8px 14px',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Clock size={15} /> Frise 2126
          </button>

          <button
            onClick={() => {
              setGuideInitialContext(null);
              setIsGuideOpen(true);
            }}
            style={{
              marginLeft: '8px',
              background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
              border: 'none',
              color: '#050714',
              padding: '8px 16px',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: '0 4px 12px rgba(245, 158, 11, 0.3)'
            }}
          >
            <MessageSquare size={15} /> Guide IA
          </button>
        </nav>
      </header>

      {/* ── Main View Switcher ────────────────────────────────────────── */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* VIEW 1: HOME / LANDING (Page 1 PDF) */}
        {currentView === 'home' && (
          <div style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '60px 24px',
            textAlign: 'center',
            position: 'relative',
            background: 'radial-gradient(circle at 50% 40%, rgba(59, 130, 246, 0.08) 0%, transparent 60%)'
          }}>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              background: 'rgba(56, 189, 248, 0.1)',
              color: '#38bdf8',
              padding: '6px 14px',
              borderRadius: '20px',
              fontSize: '12px',
              fontWeight: 700,
              letterSpacing: '0.08em',
              marginBottom: '20px'
            }}>
              EXPOSITION PERMANENTE · 2026 → 2126
            </div>

            <h1 style={{
              fontSize: 'clamp(2.8rem, 6vw, 4.5rem)',
              fontWeight: 900,
              lineHeight: 1.1,
              maxWidth: '850px',
              marginBottom: '18px',
              background: 'linear-gradient(135deg, #ffffff 0%, #cbd5e1 50%, #94a3b8 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent'
            }}>
              AI Museum of the Future
            </h1>

            <p style={{
              fontSize: '18px',
              color: '#94a3b8',
              maxWidth: '620px',
              lineHeight: 1.6,
              marginBottom: '10px'
            }}>
              {exhibitionData?.subtitle || "Comment le futur se souviendra de notre époque."}
            </p>

            <p style={{
              fontSize: '14px',
              color: '#f59e0b',
              fontStyle: 'italic',
              marginBottom: '40px'
            }}>
              [{exhibitionData?.title || "Titre de l'exposition généré par le Curator Agent"}]
            </p>

            {/* CTA Buttons */}
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', justifyContent: 'center', marginBottom: '60px' }}>
              <button
                onClick={() => setCurrentView('plan')}
                style={{
                  background: 'linear-gradient(135deg, #f59e0b 0%, #ea580c 100%)',
                  border: 'none',
                  color: '#050714',
                  padding: '16px 36px',
                  borderRadius: '12px',
                  fontSize: '15px',
                  fontWeight: 800,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  boxShadow: '0 8px 25px rgba(245, 158, 11, 0.4)',
                  transition: 'transform 0.2s'
                }}
              >
                Entrer dans le musée <ArrowRight size={18} />
              </button>

              <button
                onClick={() => {
                  setGuideInitialContext(null);
                  setIsGuideOpen(true);
                }}
                style={{
                  background: 'rgba(30, 41, 59, 0.6)',
                  border: '1px solid var(--border-subtle)',
                  color: '#e2e8f0',
                  padding: '16px 28px',
                  borderRadius: '12px',
                  fontSize: '15px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  backdropFilter: 'blur(8px)'
                }}
              >
                Ou demander au conservateur IA
              </button>
            </div>

            {/* Pipeline Step Ribbon */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              fontSize: '12px',
              color: '#64748b',
              background: 'rgba(15, 23, 42, 0.6)',
              padding: '10px 24px',
              borderRadius: '30px',
              border: '1px solid var(--border-subtle)'
            }}>
              <span>Sources publiques</span>
              <span>→</span>
              <span>n8n</span>
              <span>→</span>
              <span>RAG</span>
              <span>→</span>
              <span style={{ color: '#38bdf8', fontWeight: 600 }}>5 agents</span>
              <span>→</span>
              <span style={{ color: '#f59e0b', fontWeight: 700 }}>Curateur</span>
            </div>
          </div>
        )}

        {/* VIEW 2: PLAN DU MUSÉE (Page 2 PDF) */}
        {currentView === 'plan' && (
          <div style={{ maxWidth: '1200px', width: '100%', margin: '0 auto', padding: '32px 24px', flex: 1 }}>
            <MuseumPlanView 
              rooms={exhibitionData?.rooms || []}
              selectedRoom={selectedRoom}
              onSelectRoom={(room) => setSelectedRoom(room)}
              onEnter3D={handleEnter3D}
            />
          </div>
        )}

        {/* VIEW 3: 3D INTERACTIVE GALLERY (Page 3 PDF) */}
        {currentView === 'museum3d' && (
          <div style={{ flex: 1, position: 'relative', width: '100%', height: 'calc(100vh - 65px)' }}>
            {/* Top 3D HUD */}
            <div style={{
              position: 'absolute',
              top: '20px',
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 100,
              background: 'rgba(10, 14, 39, 0.85)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '12px',
              padding: '10px 24px',
              backdropFilter: 'blur(12px)',
              textAlign: 'center'
            }}>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#f8fafc' }}>
                Salle : {selectedRoom?.name || 'Technologie'}
              </h3>
              <p style={{ fontSize: '11px', color: '#94a3b8' }}>
                Agent responsable : {selectedRoom?.agent || 'Technologue'} · {selectedRoom?.total_items || 12} artefacts exposés
              </p>
            </div>

            <MuseumScene3D 
              featuredItems={selectedRoom?.featured || []}
              onSelectArtifact={handleOpenArtifactFrom3D}
            />
          </div>
        )}

        {/* VIEW 4: TIMELINE (Page 6 PDF) */}
        {currentView === 'timeline' && (
          <div style={{ maxWidth: '1100px', width: '100%', margin: '0 auto', padding: '32px 24px', flex: 1 }}>
            <TimelineView 
              events={timelineEvents}
              onOpenArtifact={(ev) => handleOpenArtifactFrom3D(ev)}
            />
          </div>
        )}
      </main>

      {/* ── MODAL: Artifact Detail (Page 4 PDF) ─────────────────────── */}
      <ArtifactDetailModal 
        artifact={selectedArtifact}
        onClose={() => setSelectedArtifact(null)}
        onAskGuide={handleAskGuideFromArtifact}
      />

      {/* ── MODAL: Curator AI Guide (Page 5 PDF) ────────────────────── */}
      <GuideChatModal 
        isOpen={isGuideOpen}
        onClose={() => setIsGuideOpen(false)}
        initialContext={guideInitialContext}
      />
    </div>
  );
}
