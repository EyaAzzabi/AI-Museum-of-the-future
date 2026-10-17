import React, { useState } from 'react';
import { Clock, Calendar, ArrowRight, ShieldCheck, Sparkles } from 'lucide-react';

export default function TimelineView({ events = [], onOpenArtifact }) {
  const [selectedEvent, setSelectedEvent] = useState(events[0] || null);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '30px', padding: '24px 0' }}>
      {/* Intro */}
      <div style={{ textAlign: 'center', maxWidth: '700px', margin: '0 auto' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'rgba(56, 189, 248, 0.1)', color: '#38bdf8', padding: '4px 12px', borderRadius: '20px', fontSize: '12px', fontWeight: 600, marginBottom: '12px' }}>
          <Clock size={14} /> FRISE 2026 → 2126 : LE REGARD DU MUSÉE
        </div>
        <h2 style={{ fontSize: '28px', fontWeight: 800, color: '#f8fafc', marginBottom: '8px' }}>
          Comment les événements de 2026 ont façonné notre siècle
        </h2>
        <p style={{ color: '#94a3b8', fontSize: '14px', lineHeight: '1.6' }}>
          Découvrez le verdict rétrospectif formulé depuis 2126 par nos agents spécialisés sur les tournants de l'année 2026.
        </p>
      </div>

      {/* Timeline track */}
      <div style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '30px 20px',
        margin: '20px 0',
        background: 'rgba(15, 23, 42, 0.6)',
        borderRadius: '16px',
        border: '1px solid var(--border-subtle)',
        overflowX: 'auto'
      }}>
        {/* Horizontal connecting line */}
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '40px',
          right: '40px',
          height: '2px',
          background: 'linear-gradient(90deg, #3b82f6 0%, #a855f7 50%, #10b981 100%)',
          zIndex: 0
        }} />

        {events.map((ev, i) => {
          const isSelected = selectedEvent?.id === ev.id;
          return (
            <div
              key={ev.id || i}
              onClick={() => setSelectedEvent(ev)}
              style={{
                position: 'relative',
                zIndex: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                cursor: 'pointer',
                minWidth: '120px'
              }}
            >
              <div style={{
                width: isSelected ? '34px' : '24px',
                height: isSelected ? '34px' : '24px',
                borderRadius: '50%',
                background: isSelected ? ev.color : 'rgba(30, 41, 59, 0.9)',
                border: `3px solid ${ev.color || '#3b82f6'}`,
                boxShadow: isSelected ? `0 0 20px ${ev.color}` : 'none',
                transition: 'all 0.3s ease',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '10px'
              }}>
                {isSelected && <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#fff' }} />}
              </div>
              <div style={{
                fontSize: '12px',
                fontWeight: isSelected ? 700 : 500,
                color: isSelected ? '#f8fafc' : '#94a3b8',
                textAlign: 'center',
                transition: 'color 0.2s'
              }}>
                {ev.date}
              </div>
              <div style={{
                fontSize: '11px',
                color: ev.color,
                fontWeight: 600,
                marginTop: '2px'
              }}>
                {ev.room_name}
              </div>
            </div>
          );
        })}
      </div>

      {/* Selected Event Card (Verdict) */}
      {selectedEvent && (
        <div className="glass-panel" style={{
          padding: '28px',
          borderLeft: `4px solid ${selectedEvent.color || '#3b82f6'}`,
          maxWidth: '850px',
          margin: '0 auto',
          width: '100%'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
            <div>
              <span style={{
                background: `${selectedEvent.color}25`,
                color: selectedEvent.color,
                padding: '3px 10px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 700,
                textTransform: 'uppercase'
              }}>
                {selectedEvent.room_name} · {selectedEvent.date}
              </span>
              <h3 style={{ fontSize: '22px', fontWeight: 700, color: '#f8fafc', marginTop: '10px' }}>
                {selectedEvent.title}
              </h3>
            </div>
          </div>

          <p style={{ fontSize: '14.5px', color: '#cbd5e1', lineHeight: '1.6', marginBottom: '20px' }}>
            {selectedEvent.summary}
          </p>

          {/* Verdict Box */}
          <div style={{
            background: 'rgba(5, 7, 20, 0.6)',
            padding: '16px 20px',
            borderRadius: '10px',
            border: '1px solid var(--border-subtle)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#fbbf24', fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>
              <ShieldCheck size={16} />
              VERDICT DE L'AGENT {selectedEvent.verdict_agent.toUpperCase()} (DEPUIS 2126) :
            </div>
            <p style={{ fontSize: '14px', fontStyle: 'italic', color: '#e2e8f0', lineHeight: '1.5' }}>
              « {selectedEvent.verdict_text} »
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
