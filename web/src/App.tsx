import { BookOpen01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { AnswerView } from "@/components/ask/answer-view"
import { AskForm } from "@/components/ask/ask-form"
import { FailureAlert } from "@/components/ask/failure-alert"
import { ProgressPanel } from "@/components/ask/progress-panel"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
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
    <main className="mx-auto flex h-svh w-full max-w-3xl flex-col p-4">
      <Card className="min-h-0 flex-1">
        <CardHeader>
          <CardTitle>Agente de biblioteca</CardTitle>
          <CardDescription>Consultá en castellano o inglés; el agente indica de dónde sale cada respuesta.</CardDescription>
        </CardHeader>
        <CardContent className="min-h-0 flex-1 overflow-hidden p-0">
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
                  <MessageScrollerContent className="p-(--card-spacing)">
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
        </CardContent>
        <CardFooter>
          <AskForm running={running} onSubmit={(question) => void ask(question)} onCancel={cancel} />
        </CardFooter>
      </Card>
    </main>
  )
}

export default App
