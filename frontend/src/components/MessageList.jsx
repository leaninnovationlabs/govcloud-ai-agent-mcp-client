import { useEffect, useRef } from 'react'
import { User, Bot } from 'lucide-react'

export const MessageList = ({ messages, loading, thinking }) => {
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4 custom-scrollbar">
      {messages.length === 0 && !loading ? (
        <div className="flex items-center justify-center h-full">
          <div className="text-center max-w-md mx-auto animate-in fade-in zoom-in duration-700">
            <div className="relative inline-block mb-6">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center">
                <Bot className="h-8 w-8 text-gray-700" />
              </div>
            </div>
            <h3 className="text-xl font-light text-gray-900 mb-3 tracking-tight">
              GovCloud Intelligence Platform
            </h3>
            <p className="text-sm text-gray-600 leading-relaxed">
              Secure communication channel ready. Your conversations are protected by federal-grade encryption protocols.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {messages.map((message, index) => (
            <div
              key={message.id}
              className={`flex gap-3 animate-in slide-in-from-bottom duration-500 ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
              style={{ animationDelay: `${Math.min(index * 50, 200)}ms` }}
            >
              {message.role === 'ai' && (
                <div className="flex-shrink-0 w-9 h-9 bg-gray-900 rounded-full flex items-center justify-center">
                  <Bot className="h-5 w-5 text-white" />
                </div>
              )}
              
              <div
                className={`max-w-3xl rounded-2xl px-5 py-3 shadow-sm transition-shadow duration-200 hover:shadow-md ${
                  message.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-gray-900 border border-gray-200'
                }`}
              >
                <div className="whitespace-pre-wrap text-sm leading-relaxed">
                  {message.content || (message.role === 'ai' && thinking && index === messages.length - 1 ? (
                    <div className="flex items-center gap-0.5 py-0.5">
                      <span className="inline-block text-gray-600 animate-typing">•</span>
                      <span className="inline-block text-gray-600 animate-typing" style={{ animationDelay: '0.15s' }}>•</span>
                      <span className="inline-block text-gray-600 animate-typing" style={{ animationDelay: '0.3s' }}>•</span>
                    </div>
                  ) : '')}
                </div>
              </div>

              {message.role === 'user' && (
                <div className="flex-shrink-0 w-9 h-9 bg-gray-600 rounded-full flex items-center justify-center">
                  <User className="h-5 w-5 text-white" />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      <div ref={messagesEndRef} />
    </div>
  )
}