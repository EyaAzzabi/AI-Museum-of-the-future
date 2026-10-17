import React from 'react';
import { ArrowRight, Sparkles, BookOpen, Layers } from 'lucide-react';

export default function MuseumPlanView({ rooms = [], selectedRoom, onSelectRoom, onEnter3D }) {
  const currentRoom = selectedRoom || rooms[0];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '32px', padding: '16px 0' }}>
      {/* Left: Rooms Grid Plan */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#38bdf8', letterSpacing: '0.05em' }}>
            PLAN ARCHITECTURAL DU MUSÉE
          </span>
          <h2 style={{ fontSize: '26px', fontWeight: 800, color: '#f8fafc', marginTop: '4px' }}>
            5 Salles thématiques · 5 Perspectives d'agents
          </h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '14px' }}>
          {rooms.map((room) => {
            const isSelected = currentRoom?.id === room.id;
            return (
              <div
                key={room.id}
                onClick={() => onSelectRoom(room)}
                className="glass-panel"
                style={{
                  padding: '20px',
                  cursor: 'pointer',
                  border: `1.5px solid ${isSelected ? room.accent_color : 'var(--border-subtle)'}`,
                  background: isSelected ? 'rgba(30, 41, 89, 0.6)' : 'rgba(15, 23, 42, 0.4)',
                  boxShadow: isSelected ? `0 0 20px ${room.accent_color}33` : 'none',
                  transition: 'all 0.25s ease',
                  position: 'relative',
                  overflow: 'hidden'
                }}
              >
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '4px',
                  height: '100%',
                  backgroundColor: room.accent_color || '#3b82f6'
                }} />
                <div style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '6px' }}>
                  AGENT {room.agent.toUpperCase()}
                </div>
                <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc', marginBottom: '8px' }}>
                  {room.name}
                </h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '12px', color: '#cbd5e1' }}>
                  <span>📦 {room.total_items || 12} artefacts</span>
                  <span>•</span>
                  <span style={{ color: '#38bdf8' }}>RAG Actif</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right: Selected Room Inspector */}
      {currentRoom && (
        <div className="glass-panel" style={{
          padding: '30px',
          display: 'flex',
          flexDirection: 'column',
          gap: '20px',
          borderLeft: `4px solid ${currentRoom.accent_color || '#3b82f6'}`
        }}>
          <div>
            <span style={{
              background: `${currentRoom.accent_color}25`,
              color: currentRoom.accent_color,
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 700,
              textTransform: 'uppercase'
            }}>
              SALLE SÉLECTIONNÉE
            </span>
            <h2 style={{ fontSize: '28px', fontWeight: 800, color: '#f8fafc', marginTop: '8px' }}>
              {currentRoom.name}
            </h2>
            <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
              Agent responsable : <strong>{currentRoom.agent}</strong>
            </p>
          </div>

          <p style={{ fontSize: '14px', color: '#cbd5e1', lineHeight: '1.6' }}>
            {currentRoom.description || "Exploration rigoureuse des corpus et des dynamiques contemporaines générée par l'agent à partir du corpus RAG."}
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
            <div style={{ background: 'rgba(5, 7, 20, 0.5)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '22px', fontWeight: 800, color: '#f8fafc' }}>{currentRoom.total_items}</div>
              <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase' }}>Objets catalogués</div>
            </div>
            <div style={{ background: 'rgba(5, 7, 20, 0.5)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '22px', fontWeight: 800, color: currentRoom.accent_color }}>100%</div>
              <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase' }}>Alignement RAG</div>
            </div>
          </div>

          {/* Featured items */}
          {currentRoom.featured && currentRoom.featured.length > 0 && (
            <div>
              <div style={{ fontSize: '12px', fontWeight: 700, color: '#94a3b8', marginBottom: '10px' }}>
                OBJETS À LA UNE
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {currentRoom.featured.slice(0, 3).map((item, idx) => (
                  <div key={idx} style={{
                    padding: '10px 14px',
                    background: 'rgba(255, 255, 255, 0.03)',
                    borderRadius: '6px',
                    border: '1px solid var(--border-subtle)',
                    fontSize: '13px',
                    color: '#e2e8f0',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}>
                    <span style={{ color: currentRoom.accent_color }}>✦</span>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.title}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button
            onClick={() => onEnter3D(currentRoom)}
            style={{
              marginTop: 'auto',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '10px',
              padding: '14px 20px',
              borderRadius: '10px',
              background: `linear-gradient(135deg, ${currentRoom.accent_color || '#3b82f6'} 0%, #2563eb 100%)`,
              border: 'none',
              color: 'white',
              fontSize: '14px',
              fontWeight: 700,
              cursor: 'pointer',
              boxShadow: `0 8px 20px ${currentRoom.accent_color || '#3b82f6'}44`,
              transition: 'transform 0.2s'
            }}
          >
            Entrer dans la salle 3D <ArrowRight size={18} />
          </button>
        </div>
      )}
    </div>
  );
}
