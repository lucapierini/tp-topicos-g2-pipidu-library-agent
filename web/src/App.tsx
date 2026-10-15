import { BookOpen01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { AnswerView } from "@/components/ask/answer-view"
import { AskForm } from "@/components/ask/ask-form"
import { FailureAlert } from "@/components/ask/failure-alert"
import { ProgressPanel } from "@/components/ask/progress-panel"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Message, MessageContent } from "@/components/ui/message"
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller"
import { useAsk, type AskState } from "@/hooks/use-ask"

type TurnState = Exclude<AskState, { status: "idle" }>

function Turn({ turn, latest, onRetry }: { turn: TurnState; latest: boolean; onRetry: (question: string) => void }) {
  return (
    <>
      <MessageScrollerItem scrollAnchor={latest}>
        <Message align="end">
          <MessageContent>
            <Bubble>
              <BubbleContent className="whitespace-pre-wrap">{turn.question}</BubbleContent>
            </Bubble>
          </MessageContent>
        </Message>
      </MessageScrollerItem>
      <MessageScrollerItem>
        <Message>
          <MessageContent>
            {turn.status === "running" ? (
              <ProgressPanel progress={turn.progress} elapsed={turn.elapsed} />
            ) : turn.status === "done" ? (
              <AnswerView result={turn.result} />
            ) : (
              <FailureAlert kind={turn.kind} message={turn.message} onRetry={() => onRetry(turn.question)} />
            )}
          </MessageContent>
        </Message>
      </MessageScrollerItem>
    </>
  )
}

export function App() {
  const { state, history, ask, cancel } = useAsk()
  const running = state.status === "running"
  const turns: TurnState[] = state.status === "idle" ? history : [...history, state]

  return (
    <main className="flex h-svh w-full flex-col">
      <header className="shrink-0 border-b">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-0.5 px-4 py-3">
          <h1 className="text-base font-medium">Agente de biblioteca</h1>
          <p className="text-sm text-muted-foreground">
            Consultá en castellano o inglés; el agente indica de dónde sale cada respuesta.
          </p>
        </div>
      </header>
      <div className="min-h-0 flex-1">
        {turns.length === 0 ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <HugeiconsIcon icon={BookOpen01Icon} />
              </EmptyMedia>
              <EmptyTitle>Hacé una consulta</EmptyTitle>
              <EmptyDescription>
                Por ejemplo: «¿Qué préstamos vencen esta semana?» o «¿Cuántos días dura un préstamo?»
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <MessageScrollerProvider>
            <MessageScroller>
              <MessageScrollerViewport>
                <MessageScrollerContent className="mx-auto w-full max-w-3xl p-4">
                  {turns.map((turn, index) => (
                    <Turn
                      key={index}
                      turn={turn}
                      latest={index === turns.length - 1}
                      onRetry={(question) => void ask(question, { retry: true })}
                    />
                  ))}
                </MessageScrollerContent>
              </MessageScrollerViewport>
              <MessageScrollerButton />
            </MessageScroller>
          </MessageScrollerProvider>
        )}
      </div>
      <footer className="shrink-0">
        <div className="mx-auto w-full max-w-3xl px-4 pt-2 pb-4">
          <AskForm running={running} onSubmit={(question) => void ask(question)} onCancel={cancel} />
        </div>
      </footer>
    </main>
  )
}

export default App
