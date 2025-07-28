import { useEffect } from 'react'
import { useShallow } from 'zustand/react/shallow'
import useChatStore from './store'

export const useChat = () => {
    const [
        ready,
        messages,
        conversations,
        currentConversationId,
        loading,
        thinking,
        input,
        error,
        init,
        setInput,
        sendMessage,
        selectConversation,
        createNewConversation,
        clearConversation,
        clearError
    ] = useChatStore(
        useShallow((state) => [
            state.ready,
            state.messages,
            state.conversations,
            state.currentConversationId,
            state.loading,
            state.thinking,
            state.input,
            state.error,
            state.init,
            state.setInput,
            state.sendMessage,
            state.selectConversation,
            state.createNewConversation,
            state.clearConversation,
            state.clearError
        ])
    )

    useEffect(() => {
        if (!ready) {
            init()
        }
    }, [ready, init])

    const handleSubmit = async (e) => {
        e?.preventDefault()
        if (input.trim() && !thinking) {
            await sendMessage()
        }
    }

    const handleInputChange = (value) => {
        setInput(value)
        if (error) clearError()
    }

    return {
        ready,
        messages,
        conversations,
        currentConversationId,
        loading,
        thinking,
        input,
        error,
        handleSubmit,
        handleInputChange,
        selectConversation,
        createNewConversation,
        clearConversation
    }
}