import React, { useState, useEffect, useRef } from 'react';
import { X, Send, Bot, Sparkles, BookOpen } from 'lucide-react';
import { askGuideChat } from '../services/api';

export default function GuideChatModal({ isOpen, onClose, initialContext }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Bienvenue ! Je suis le Conservateur IA du musée. Avec le concours de nos 5 agents spécialisés (Historien, Sociologue, Technologue, Culture & Art, Visuel), je peux vous guider ou éclairer les mémoires de l'année 2026. Que souhaitez-vous explorer ?"
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (initialContext) {
      handleSend(`Pouvez-vous me donner la perspective du Conservateur sur « ${initialContext.title} » ?`);
    }
  }, [initialContext]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  if (!isOpen) return null;

  const handleSend = async (customText = null) => {
    const textToSend = customText || input;
    if (!textToSend.trim() || loading) return;

    const newMessages = [...messages, { role: 'user', content: textToSend }];
    setMessages(newMessages);
    if (!customText) setInput('');
    setLoading(true);

    try {
      const data = await askGuideChat(textToSend, newMessages);
      setMessages([...newMessages, {
        role: 'assistant',
        content: data.reply,
        sources: data.sources || []
      }]);
    } catch (err) {
      setMessages([...newMessages, {
        role: 'assistant',
        content: "Désolé, une anomalie temporaire de liaison avec les agents est survenue. Veuillez reformuler votre question."
      }]);
    } finally {
      setLoading(false);
    }
  };

  const suggestions = [
    "Que retiendrait-on de l'intelligence artificielle dans 100 ans ?",
    "Lance une visite express en 5 objets phares",
    "Résume la salle Société et ses tensions en 2026"
  ];

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100vw',
      height: '100vh',
      backgroundColor: 'rgba(5, 7, 20, 0.75)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1100,
      padding: '20px'
    }}>
      <div className="glass-panel" style={{
        width: '100%',
        maxWidth: '680px',
        height: '80vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 25px 50px rgba(0, 0, 0, 0.7)',
        border: '1px solid rgba(139, 92, 246, 0.4)'
      }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '16px 24px',
          borderBottom: '1px solid var(--border-subtle)',
          background: 'rgba(26, 16, 60, 0.5)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 16px rgba(245, 158, 11, 0.4)'
            }}>
              <Bot size={20} color="#fff" />
            </div>
            <div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#f8fafc' }}>
                Le Conservateur IA
              </h3>
              <p style={{ fontSize: '11px', color: '#10b981', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
                En ligne · RAG + 5 agents spécialisés
              </p>
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        {/* Messages List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {messages.map((m, idx) => (
            <div
              key={idx}
              style={{
                alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '82%',
                backgroundColor: m.role === 'user' ? 'rgba(99, 102, 241, 0.3)' : 'rgba(30, 41, 59, 0.7)',
                border: `1px solid ${m.role === 'user' ? 'rgba(99, 102, 241, 0.5)' : 'rgba(148, 163, 184, 0.15)'}`,
                padding: '12px 16px',
                borderRadius: m.role === 'user' ? '14px 14px 2px 14px' : '14px 14px 14px 2px',
                color: '#e2e8f0',
                fontSize: '13.5px',
                lineHeight: '1.55'
              }}
            >
              {m.content}
              {m.sources && m.sources.length > 0 && (
                <div style={{ marginTop: '8px', paddingTop: '6px', borderTop: '1px solid rgba(255,255,255,0.1)', fontSize: '11px', color: '#38bdf8', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  <BookOpen size={12} /> Sources RAG : {m.sources.map((s, i) => <span key={i} style={{ background: 'rgba(56, 189, 248, 0.15)', padding: '1px 6px', borderRadius: '4px' }}>[{s}]</span>)}
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div style={{ alignSelf: 'flex-start', padding: '10px 16px', background: 'rgba(30, 41, 59, 0.5)', borderRadius: '14px', fontSize: '13px', color: '#94a3b8' }}>
              Le Conservateur consulte le RAG et synthétise...
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Suggestions */}
        <div style={{ padding: '0 16px 8px 16px', display: 'flex', gap: '6px', overflowX: 'auto' }}>
          {suggestions.map((s, i) => (
            <button
              key={i}
              onClick={() => handleSend(s)}
              style={{
                whiteSpace: 'nowrap',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid var(--border-subtle)',
                color: '#94a3b8',
                padding: '6px 12px',
                borderRadius: '16px',
                fontSize: '11px',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Input bar */}
        <div style={{ padding: '14px 18px', borderTop: '1px solid var(--border-subtle)', display: 'flex', gap: '10px' }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Posez une question au Conservateur..."
            style={{
              flex: 1,
              background: 'rgba(15, 23, 42, 0.8)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              padding: '10px 14px',
              color: '#f8fafc',
              fontSize: '13px',
              outline: 'none'
            }}
          />
          <button
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
            style={{
              background: '#f59e0b',
              border: 'none',
              color: '#050714',
              padding: '10px 16px',
              borderRadius: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
