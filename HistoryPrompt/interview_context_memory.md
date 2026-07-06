# Travel Planning Assistant Interview Context Memory

## Project Background

This project is a Travel Planning Assistant with a FastAPI backend and Vue/Vite frontend.

The backend generates travel itineraries from user inputs such as destination, travel dates, travelers, budget level, travel pace, interests, and dietary notes. The core itinerary API is:

```text
POST /api/v1/itineraries/plan
```

The backend returns a structured `ItineraryPlan`, including daily plans, attractions, restaurants, hotels, budget breakdown, map route, weather context, and travel advice.

The current backend uses:

- FastAPI for API routes
- Pydantic models for structured request/response data
- LangGraph for workflow orchestration
- MCP-style tools/services for AMap search and weather
- UApiPro as primary weather provider
- AMap as fallback weather/search provider
- Pexels for itinerary photos
- Local service fallback when the Agent workflow fails

Important files:

- `backend/app/api/routes.py`
- `backend/app/agents/planner_agent.py`
- `backend/app/agents/weather_query_agent.py`
- `backend/app/agents/attraction_search_agent.py`
- `backend/app/agents/hotel_agent.py`
- `backend/app/services/itinerary_optimizer.py`
- `backend/tests/`
- `frontend/src/services/planner.test.ts`

## Function Calling

Function Calling is a mechanism that lets an LLM output a structured tool/function call instead of only natural language.

The model does not directly execute code. It only decides:

- Whether a tool should be called
- Which tool should be called
- What arguments should be passed

The application backend executes the real function/API/database operation and returns the result to the model.

Typical flow:

```text
User request
  -> App sends tool schemas to model
  -> Model emits tool/function call with structured arguments
  -> Backend executes the function
  -> Backend sends tool result back to model
  -> Model generates final response
```

For the travel assistant, examples of function/tool calls include:

- Search attractions
- Find hotels
- Query weather
- Optimize route
- Generate travel advice

Key interview point:

> Function Calling is not the model running code. It is a structured protocol between the model and the application. Real execution, validation, permission control, retry, timeout, and error handling belong to the application layer.

## Workflow

Workflow means splitting a complex AI task into multiple controllable steps and defining their execution order, state passing, fallback logic, and final output.

In this project, itinerary generation is not a single LLM call. It is a multi-step workflow:

```text
User travel request
  -> Search attractions
  -> Find hotels
  -> Query weather
  -> Generate itinerary plan
  -> Return structured ItineraryPlan
```

The workflow is implemented with LangGraph in `backend/app/agents/planner_agent.py`.

Core code pattern:

```python
workflow = StateGraph(AgentState)

workflow.add_node("search_attractions", _search_attractions_node)
workflow.add_node("find_hotels", _find_hotels_node)
workflow.add_node("check_weather", _check_weather_node)
workflow.add_node("generate_plan", _generate_plan)

workflow.set_entry_point("search_attractions")
workflow.add_edge("search_attractions", "find_hotels")
workflow.add_edge("find_hotels", "check_weather")
workflow.add_edge("check_weather", "generate_plan")
workflow.add_edge("generate_plan", END)
```

Core concepts:

- State: shared workflow context, represented by `AgentState`
- Node: one processing step, such as attraction search or weather query
- Edge: transition between nodes
- Tool/Service: external capability used by nodes
- Fallback: graceful degradation when a node or provider fails

`AgentState` carries intermediate results such as:

- Request data
- Destination
- Travel dates
- Preferences
- Attraction data
- Hotel data
- Weather data
- Final plan
- Errors

Good interview summary:

> Workflow is the orchestration layer of an Agent application. It turns a vague user request into a stable multi-step business process. In my project, LangGraph coordinates attraction search, hotel search, weather query, route optimization, and final itinerary generation through a shared state graph.

## Weather Failure Handling

Weather is treated as enhancement data, not a hard blocker. If weather lookup fails, the system should still generate a usable itinerary and clearly mark weather as unavailable.

The project has three layers of fallback.

### 1. Weather Provider Fallback

Implemented in `backend/app/agents/weather_query_agent.py`.

Flow:

```text
Try UApiPro weather
  -> If failed, try AMap weather
  -> If failed, return unavailable WeatherContext
```

If all providers fail, the system returns structured unavailable weather data:

```python
WeatherContext(
    city=destination,
    source="none",
    forecasts=[
        WeatherForecast(
            available=False,
            unavailable_reason="..."
        )
    ]
)
```

This avoids fabricating weather and avoids crashing the itinerary workflow.

### 2. Workflow Node Fallback

In `planner_agent.py`, `_check_weather_node()` wraps weather query in `try/except`.

If unexpected exceptions occur, it returns:

- Empty/none weather context
- Error message in workflow state

The workflow continues.

### 3. API-Level Fallback

In `backend/app/api/routes.py`, the route catches full Agent workflow failure:

```python
try:
    plan = await planner_agent.run(request)
except Exception:
    plan = itinerary_service.generate_plan(request)
```

So the overall fallback chain is:

```text
UApiPro fails
  -> AMap fallback
  -> unavailable WeatherContext
  -> weather node fallback
  -> full itinerary_service fallback
```

Interview summary:

> Weather failure does not block itinerary generation. The system uses provider fallback, structured unavailable weather, workflow-level error capture, and API-level default itinerary fallback to preserve user experience.

## LangChain And LangGraph

LangChain is a framework for building LLM and Agent applications. It provides:

- Model abstraction
- Prompt templates
- Tools
- Agent loops
- RAG utilities
- Structured output
- Memory
- Middleware/guardrails
- Observability through LangSmith

Typical LangChain Agent flow:

```text
User input
  -> LLM decides whether to call a tool
  -> Tool executes
  -> Tool result returns to LLM
  -> LLM decides next step or final answer
```

Minimal conceptual example:

```python
from langchain.agents import create_agent
from langchain.tools import tool

@tool
def query_weather(city: str) -> str:
    """Query weather for a city."""
    return "Cloudy"

agent = create_agent(
    model="openai:gpt-4.1",
    tools=[query_weather],
    system_prompt="You are a travel planning assistant.",
)
```

This project does not directly use LangChain Agent. It uses LangGraph:

```python
from langgraph.graph import END, StateGraph
```

LangGraph belongs to the LangChain ecosystem but has a different role.

Main difference:

```text
LangChain Agent:
  Model-driven tool-calling loop.
  The LLM decides which tool to call and when.

LangGraph:
  Developer-defined workflow/state machine.
  The developer explicitly defines nodes, state, edges, and flow.
```

Comparison:

| Dimension | LangChain Agent | Project's LangGraph |
| --- | --- | --- |
| Core role | Agent/tool-calling framework | Workflow/state graph orchestration |
| Control | More model-driven | More developer-controlled |
| Flow | LLM -> Tool -> LLM loop | Node -> Edge -> State |
| Best for | Dynamic Q&A, general agents, RAG agents | Multi-step business processes |
| Reliability | Depends more on prompt/tool descriptions | Easier to test and control |
| Project fit | Could wrap tools | Better for deterministic travel workflow |

Why LangGraph fits this project:

- Travel planning is a structured business workflow
- The system needs stable steps and fallback behavior
- Weather should not be hallucinated
- Route, budget, and schedule logic should be deterministic
- The final result must be structured as `ItineraryPlan`

Interview summary:

> LangChain is suitable for building tool-calling agents where the model dynamically decides actions. My project uses LangGraph because travel planning is a multi-step workflow that benefits from explicit state, nodes, edges, and fallback handling.

## Testing Strategy

The project has backend and frontend tests plus build checks and a real itinerary smoke test.

Current coverage mentioned:

- 14 backend tests
- 2 frontend tests

### Backend Testing

Backend tests are under `backend/tests/` and use Python `unittest`.

Key tested areas:

1. Weather parsing
2. Weather provider fallback
3. Rainy-day travel advice
4. Route proximity optimization
5. Attraction deduplication
6. Schedule/time conflict handling
7. Full planner generation
8. Weather model unavailable reason preservation

### MockTransport

`httpx.MockTransport` is used to simulate third-party weather API responses without calling real external APIs.

It tests:

```text
External weather API JSON
  -> internal WeatherContext / WeatherForecast parsing
```

This verifies auth headers, response parsing, forecast normalization, and seven-day forecast boundary handling.

### AsyncMock

`AsyncMock` is used to simulate async service behavior, especially failures.

Example scenario:

```text
fetch_uapipro_weather raises exception
  -> mcp_tool.call_tool returns AMap weather
  -> query_weather returns source="amap"
```

This proves weather fallback works.

### Rainy-Day Advice Tests

`test_travel_advice.py` verifies rain weather generates advice such as:

- Carry umbrella
- Pay attention to traffic
- Prefer indoor activities

It also checks that future trip forecast should override conflicting current life-index advice.

### Route And Schedule Tests

`test_itinerary_optimizer.py` verifies:

- Duplicate attractions are removed
- Non-attraction POIs such as parking lots, entrances, ticket offices, and visitor centers are filtered
- Nearby attractions remain close in optimized route order
- Rainy days prioritize indoor or suitable nearby alternatives
- Scheduled times do not overlap
- Too-late activities are dropped instead of being forced into the day

### Planner Generation Test

`test_planner_generation.py` verifies the integrated planning step:

```text
Attractions + hotels + weather
  -> complete itinerary plan
```

It checks:

- Attractions are distributed across days
- Weather is attached to matching dates
- Travel advice is generated
- Plan structure is valid

## Frontend Testing

Frontend tests are in:

```text
frontend/src/services/planner.test.ts
```

They use Vitest.

The two key tests verify:

1. Available backend forecast maps correctly into frontend display data
2. Seven-day weather unavailable reason is preserved and displayed

This tests:

```text
Backend weather JSON
  -> frontend planner adapter
  -> UI-ready weather data
```

## Type Check, Build, And Smoke Test

Frontend `package.json` includes:

```json
"build": "vue-tsc --noEmit && vite build",
"test": "vitest run"
```

`npm run build` performs:

- TypeScript/Vue type checking with `vue-tsc --noEmit`
- Production bundling with `vite build`

Smoke test:

```text
Generate a real Ma'anshan itinerary
  -> confirm core backend planning flow works
  -> verify key fields such as weather, attractions, route, budget, and plan structure
```

Interview summary:

> The backend uses unittest for deterministic business logic, MockTransport for simulated third-party weather responses, and AsyncMock for async failure/fallback paths. The tests cover weather parsing, service degradation, rainy-day advice, route proximity, attraction deduplication, schedule conflicts, and integrated planner generation. The frontend uses Vitest to test weather data adaptation. In addition, TypeScript checking, Vite production build, and a real Ma'anshan itinerary smoke test verify that the main user flow remains healthy.

## Short Interview Answer Template

If asked to summarize the project architecture:

> My Travel Planning Assistant is a FastAPI + Vue AI application. The backend uses LangGraph to orchestrate a multi-step itinerary planning workflow: search attractions, find hotels, query weather, optimize route, generate daily schedule, calculate budget, and produce travel advice. External services are wrapped as tools/services, including UApiPro weather, AMap MCP tools, and Pexels photos. The system emphasizes structured output, fallback handling, and testability. Weather failure is handled through UApiPro-to-AMap fallback, unavailable weather models, workflow-level exception handling, and API-level fallback to a default itinerary generator.

If asked about LangChain vs LangGraph:

> LangChain is better for model-driven tool-calling agents, while LangGraph is better for explicit workflow/state-machine orchestration. My project uses LangGraph because travel planning has a clear multi-step business process and needs controlled fallbacks, deterministic route/budget logic, and structured `ItineraryPlan` output.

If asked about testing:

> The project tests both isolated logic and integrated planning behavior. Backend tests use unittest, MockTransport, and AsyncMock to cover weather parsing, fallback, rainy-day advice, route optimization, deduplication, time conflicts, and planner generation. Frontend tests use Vitest to verify weather data adaptation. TypeScript checking, Vite build, and a real Ma'anshan smoke test validate the main application flow.
