export const API_BASE = 'http://localhost:8000'

export const API_ENDPOINTS = {
    CHAT: '/chat',
    CONVERSATIONS: '/conversations/',
    CONVERSATIONS_NEW: '/conversations/new',
    CONVERSATION_MESSAGES: (id) => `/conversations/${id}/messages`,
    HEALTH: '/health'
}

export const STATUS_TYPES = {
    LOADING: "loading",
    ERROR: "error",
    SUCCESS: 'success'
}

export const COLORS = {
    NAVY_PRIMARY: '#1e3a5f',
    NAVY_SECONDARY: '#2c5282',
    NAVY_ACCENT: '#3182ce',
    NAVY_LIGHT: '#4299e1',
    WHITE: '#ffffff',
    GRAY_100: '#f7fafc',
    GRAY_200: '#edf2f7',
    GRAY_300: '#e2e8f0',
    GRAY_400: '#cbd5e0',
    GRAY_500: '#a0aec0',
    GRAY_600: '#718096',
    GRAY_700: '#4a5568',
    GRAY_800: '#2d3748',
    GRAY_900: '#1a202c'
}