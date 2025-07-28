import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import API from '../../api'
import { API_ENDPOINTS, STATUS_TYPES } from '../../constants'

const INIT = {
    ready: false,
    messages: [],
    conversations: [],
    currentConversationId: null,
    loading: false,
    thinking: false,
    input: "",
    error: null,
}

const useStore = create(immer((set, get) => ({
    ...INIT,

    setInput: (input) => set(state => { state.input = input }),

    setError: (error) => set(state => { state.error = error }),

    clearError: () => set(state => { state.error = null }),

    init: async () => {
        try {
            set(state => { state.loading = true })
            await get().loadConversations()
            set(state => { state.ready = true })
        } catch (error) {
            console.error("Failed to initialize chat store:", error)
            set(state => { 
                state.error = "Failed to initialize chat"
                state.ready = true
            })
        } finally {
            set(state => { state.loading = false })
        }
    },

    loadConversations: async () => {
        try {
            const response = await API.get(API_ENDPOINTS.CONVERSATIONS)
            const conversations = response.data || []
            set(state => { state.conversations = conversations })
        } catch (error) {
            console.error("Failed to load conversations:", error)
            set(state => { state.error = "Failed to load conversations" })
        }
    },

    createNewConversation: async () => {
        try {
            const response = await API.post(API_ENDPOINTS.CONVERSATIONS_NEW)
            const conversation = response.data
            
            set(state => {
                state.conversations.unshift(conversation)
                state.currentConversationId = conversation.id
                state.messages = []
            })
            
            return conversation.id
        } catch (error) {
            console.error("Failed to create conversation:", error)
            set(state => { state.error = "Failed to create conversation" })
            throw error
        }
    },

    selectConversation: async (conversationId) => {
        if (conversationId === get().currentConversationId) return

        try {
            set(state => { 
                state.loading = true
                state.currentConversationId = conversationId
                state.messages = []
            })

            const response = await API.get(API_ENDPOINTS.CONVERSATION_MESSAGES(conversationId))
            const messages = response.data || []

            set(state => { state.messages = messages })
        } catch (error) {
            console.error("Failed to load conversation messages:", error)
            set(state => { state.error = "Failed to load conversation" })
        } finally {
            set(state => { state.loading = false })
        }
    },

    clearConversation: () => {
        set(state => {
            state.currentConversationId = null
            state.messages = []
            state.thinking = false
            state.error = null
        })
    },

    sendMessage: async () => {
        const message = get().input?.trim()
        if (!message) return

        let conversationId = get().currentConversationId

        try {
            // Create new conversation if none selected
            if (!conversationId) {
                conversationId = await get().createNewConversation()
            }

            // Clear input and add user message immediately
            set(state => {
                state.input = ""
                state.messages.push({
                    id: crypto.randomUUID(),
                    content: message,
                    role: 'user',
                    timestamp: new Date().toISOString()
                })
                state.thinking = true
                state.error = null
            })

            // Prepare AI message placeholder
            const aiMessageId = crypto.randomUUID()
            set(state => {
                state.messages.push({
                    id: aiMessageId,
                    content: "",
                    role: 'ai',
                    timestamp: new Date().toISOString()
                })
            })

            const response = await API.post(API_ENDPOINTS.CHAT, {
                message,
                conversation_id: conversationId
            }, { raw: true })

            const reader = response.body.getReader()
            const decoder = new TextDecoder()

            while (true) {
                const { value, done } = await reader.read()
                if (done) break

                const chunk = decoder.decode(value)
                const lines = chunk.split('\n').filter(line => line.trim())

                for (const line of lines) {
                    try {
                        const data = JSON.parse(line)
                        
                        if (data.blocks && data.blocks.length > 0) {
                            const content = data.blocks
                                .filter(block => block.type === 'text')
                                .map(block => block.content)
                                .join('')

                            set(state => {
                                const messageIndex = state.messages.findIndex(m => m.id === aiMessageId)
                                if (messageIndex !== -1) {
                                    state.messages[messageIndex].content = content
                                }
                            })
                        }
                    } catch (e) {
                        console.warn("Failed to parse streaming response:", e)
                    }
                }
            }

            // Refresh conversations to update any metadata
            await get().loadConversations()

        } catch (error) {
            console.error("Failed to send message:", error)
            set(state => {
                state.error = "Failed to send message"
                // Remove the failed AI message
                state.messages = state.messages.filter(m => m.role !== 'ai' || m.content)
            })
        } finally {
            set(state => { state.thinking = false })
        }
    },

    reset: () => {
        set(state => Object.assign(state, INIT))
    }
})))

export default useStore