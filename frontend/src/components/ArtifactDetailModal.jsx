import React, { useState } from 'react';
import { X, ExternalLink, Sparkles, Layers, Eye, BookOpen, Compass } from 'lucide-react';

export default function ArtifactDetailModal({ artifact, onClose, onAskGuide }) {
  const [activeTab, setActiveTab] = useState('curator');

  if (!artifact) return null;

  const agentViews = {
    curator: {
      name: "Curateur IA",
      badge: "Arbitre de l'exposition",
      text: artifact.curator_choice || "Cet artefact a été retenu pour sa résonance systémique : il incarne la tension clé de 2026 entre accélération technologique et reconfiguration du lien humain.",
    },
    historian: {
      name: "Agent Historien",
      badge: "Perspective temporelle",
      text: "Depuis 2126, cet objet marque un jalon documenté dans les archives : la formalisation d'une transition majeure après les crises de la décennie précédente.",
    },
    sociologist: {
      name: "Agent Sociologue",
      badge: "Dynamiques collectives",
      text: "L'impact sur les usages et la cohésion sociale révèle les inégalités d'accès mais aussi l'émergence d'une nouvelle communauté solidaire.",
    },
    technology: {
      name: "Agent Technologue",
      badge: "Innovation & Modèles",
      text: "Rupture architecturale significative : intégration poussée des représentations vectorielles et exécution locale à basse latence.",
    },
    culture_art: {
      name: "Agent Culture & Art",
      badge: "Esthétique & Mémoire",
      text: "Une signature visuelle et narrative qui s'affranchit des canons dominants pour affirmer une sensibilité propre à l'époque.",
    },
    visual: {
      name: "Agent Visuel",
      badge: "Analyse Multimodale",
      text: "Structure compositionnelle dynamique, contrastes froids-chauds caractéristiques de l'imagerie numérique du milieu des années 2020.",
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100vw',
      height: '100vh',
      backgroundColor: 'rgba(5, 7, 20, 0.85)',
      backdropFilter: 'blur(10px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '24px'
    }}>
      <div className="glass-panel" style={{
        width: '100%',
        maxWidth: '940px',
        maxHeight: '90vh',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        boxShadow: '0 25px 60px rgba(0, 0, 0, 0.7)',
        border: '1px solid rgba(99, 102, 241, 0.35)'
      }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          padding: '24px 28px',
          borderBottom: '1px solid var(--border-subtle)',
          background: 'linear-gradient(90deg, rgba(30, 41, 89, 0.4) 0%, rgba(15, 23, 42, 0) 100%)'
        }}>
          <div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{
                background: 'rgba(59, 130, 246, 0.2)',
                color: '#60a5fa',
                padding: '3px 10px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 600
              }}>
                Salle {artifact.category || 'Générale'}
              </span>
              <span style={{ color: 'var(--text-dim)', fontSize: '12px' }}>
                {artifact.date || 'Année 2026'} · Source : {artifact.source || 'Corpus RAG'}
              </span>
            </div>
            <h2 style={{ fontSize: '24px', fontWeight: 700, color: '#f8fafc' }}>
              {artifact.title || 'Artefact de mémoire 2026'}
            </h2>
          </div>
          <button 
            onClick={onClose}
            style={{
              background: 'rgba(255, 255, 255, 0.05)',
              border: 'none',
              color: '#94a3b8',
              padding: '8px',
              borderRadius: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'background 0.2s'
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Content Body */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: '28px', padding: '28px' }}>
          {/* Left Column: Multimodal Image & Visual Analysis */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{
              width: '100%',
              height: '240px',
              borderRadius: '12px',
              background: 'radial-gradient(circle at center, #1e293b 0%, #0f172a 100%)',
              border: '1px solid var(--border-subtle)',
              overflow: 'hidden',
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              {artifact.image_url ? (
                <img 
                  src={artifact.image_url} 
                  alt={artifact.title} 
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  onError={(e) => { e.target.style.display = 'none'; }}
                />
              ) : (
                <div style={{ textAlign: 'center', padding: '20px', color: '#64748b' }}>
                  <Eye size={36} style={{ marginBottom: '8px', opacity: 0.5 }} />
                  <p style={{ fontSize: '13px' }}>Rendu visuel holographique</p>
                </div>
              )}
            </div>

            {/* Multimodal Analysis Box */}
            <div className="glass-panel" style={{ padding: '16px', background: 'rgba(15, 23, 42, 0.6)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#38bdf8', fontSize: '12px', fontWeight: 600, marginBottom: '6px' }}>
                <Eye size={14} />
                MODULE MULTIMODAL · ANALYSE DE L'ARTEFACT
              </div>
              <p style={{ fontSize: '13px', color: '#cbd5e1', lineHeight: '1.5' }}>
                {artifact.text ? artifact.text.slice(0, 220) + '...' : "Présence d'éléments iconographiques clés, symbolisant les transitions énergétiques et technologiques de 2026."}
              </p>
            </div>
          </div>

          {/* Right Column: Agent Perspectives */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div>
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', letterSpacing: '0.05em', marginBottom: '8px' }}>
                VU PAR LES AGENTS SPÉCIALISÉS
              </div>
              {/* Agent Tabs */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {Object.keys(agentViews).map((key) => (
                  <button
                    key={key}
                    onClick={() => setActiveTab(key)}
                    style={{
                      background: activeTab === key ? 'rgba(99, 102, 241, 0.25)' : 'rgba(30, 41, 59, 0.5)',
                      color: activeTab === key ? '#a5b4fc' : '#94a3b8',
                      border: `1px solid ${activeTab === key ? 'rgba(99, 102, 241, 0.6)' : 'transparent'}`,
                      borderRadius: '6px',
                      padding: '6px 12px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      transition: 'all 0.2s'
                    }}
                  >
                    {agentViews[key].name}
                  </button>
                ))}
              </div>
            </div>

            {/* Selected Agent Narrative */}
            <div className="glass-panel" style={{ padding: '18px', background: 'rgba(20, 27, 65, 0.5)', borderLeft: '3px solid #6366f1' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ fontSize: '13px', fontWeight: 700, color: '#e0e7ff' }}>
                  {agentViews[activeTab].name}
                </span>
                <span style={{ fontSize: '11px', color: '#818cf8', background: 'rgba(99, 102, 241, 0.1)', padding: '2px 8px', borderRadius: '4px' }}>
                  {agentViews[activeTab].badge}
                </span>
              </div>
              <p style={{ fontSize: '14px', color: '#cbd5e1', lineHeight: '1.6' }}>
                {agentViews[activeTab].text}
              </p>
            </div>

            {/* Bottom Actions */}
            <div style={{ display: 'flex', gap: '12px', marginTop: 'auto', paddingTop: '16px' }}>
              <button 
                onClick={() => onAskGuide && onAskGuide(artifact)}
                style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                  border: 'none',
                  color: 'white',
                  padding: '12px 18px',
                  borderRadius: '8px',
                  fontWeight: 600,
                  fontSize: '13px',
                  cursor: 'pointer',
                  boxShadow: '0 4px 14px rgba(79, 70, 229, 0.35)'
                }}
              >
                <Compass size={16} /> Demander au Conservateur IA
              </button>
              {artifact.url && (
                <a
                  href={artifact.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: 'rgba(30, 41, 59, 0.8)',
                    color: '#94a3b8',
                    textDecoration: 'none',
                    padding: '12px 16px',
                    borderRadius: '8px',
                    fontSize: '13px',
                    fontWeight: 500,
                    border: '1px solid var(--border-subtle)'
                  }}
                >
                  <ExternalLink size={15} /> Source
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
