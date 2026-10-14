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
import { useAsk } from "@/hooks/use-ask"

export function App() {
  const { state, ask, cancel, reset } = useAsk()
  const running = state.status === "running"
  const lastQuestion = state.status === "idle" ? "" : state.question

  return (
    <main className="mx-auto flex h-svh w-full max-w-3xl flex-col p-4">
      <Card className="min-h-0 flex-1">
        <CardHeader>
          <CardTitle>Agente de biblioteca</CardTitle>
          <CardDescription>Consultá en castellano o inglés; el agente indica de dónde sale cada respuesta.</CardDescription>
        </CardHeader>
        <CardContent className="min-h-0 flex-1 overflow-hidden p-0">
          {state.status === "idle" ? (
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
                    <MessageScrollerItem scrollAnchor>
                      <Message align="end">
                        <MessageContent>
                          <Bubble>
                            <BubbleContent className="whitespace-pre-wrap">{state.question}</BubbleContent>
                          </Bubble>
                        </MessageContent>
                      </Message>
                    </MessageScrollerItem>
                    <MessageScrollerItem>
                      <Message>
                        <MessageContent>
                          {state.status === "running" ? (
                            <ProgressPanel progress={state.progress} elapsed={state.elapsed} />
                          ) : state.status === "done" ? (
                            <AnswerView result={state.result} />
                          ) : (
                            <FailureAlert
                              kind={state.kind}
                              message={state.message}
                              onRetry={() => void ask(state.question)}
                            />
                          )}
                        </MessageContent>
                      </Message>
                    </MessageScrollerItem>
                  </MessageScrollerContent>
                </MessageScrollerViewport>
                <MessageScrollerButton />
              </MessageScroller>
            </MessageScrollerProvider>
          )}
        </CardContent>
        <CardFooter>
          <AskForm
            key={state.status === "idle" ? "idle" : lastQuestion}
            running={running}
            initialValue=""
            onSubmit={(question) => {
              if (state.status !== "idle") reset()
              void ask(question)
            }}
            onCancel={cancel}
          />
        </CardFooter>
      </Card>
    </main>
  )
}

export default App
