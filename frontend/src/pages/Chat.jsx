import { useChat } from '../lib/store/chat/hook'
import { MessageList } from '../components/MessageList'
import { MessageInput } from '../components/MessageInput'
import { ConversationList } from '../components/ConversationList'

export const Chat = () => {
  const {
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
  } = useChat()

  if (!ready) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="relative">
            <div className="w-16 h-16 border-2 border-gray-300 rounded-full absolute animate-ping"></div>
            <div className="w-16 h-16 border-2 border-gray-800 border-t-transparent rounded-full animate-spin mx-auto"></div>
          </div>
          <p className="text-gray-600 mt-6 text-sm tracking-wide animate-pulse">Initializing Secure Interface...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex bg-white">
      <ConversationList
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={selectConversation}
        onNewConversation={() => {
          clearConversation()
          createNewConversation()
        }}
      />
      
      <div className="flex-1 flex flex-col bg-gray-50/50">
        <header className="border-b border-gray-200 bg-white px-8 py-6">
          <div>
            <h1 className="text-2xl font-light text-gray-900 tracking-tight">
              GovCloud Intelligence Platform
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              {currentConversationId ? 'Secure channel active' : 'Initialize new session'}
            </p>
          </div>
        </header>

        {error && (
          <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg animate-in slide-in-from-top duration-300">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <MessageList 
          messages={messages} 
          loading={loading} 
          thinking={thinking} 
        />

        <MessageInput
          value={input}
          onChange={handleInputChange}
          onSubmit={handleSubmit}
          disabled={thinking}
          placeholder="Type your secure message..."
        />
      </div>
    </div>
  )
}