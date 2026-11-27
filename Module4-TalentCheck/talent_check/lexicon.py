"""Keyword cues -> (skillset, level the cue implies when demonstrated in practice).

Tiers follow the level rubric (e.g. 'Docker usage' is Level 4 of DevOps & Cloud, 'BFS and DFS' Level 7
of DSA). A cue only says *what level of skill this keyword belongs to*; whether the candidate really
shows it (applied vs merely listed, hedged vs strong, confidence, internship/hackathon backing) is
decided in level_estimator.py.

Each entry: (regex-or-term, category_code, tier).  Plain terms are matched on word boundaries;
entries starting with 're:' are raw regexes.
"""
from __future__ import annotations

import re
from typing import List, Tuple

_RAW: List[Tuple[str, str, float]] = [
    # ---------------------------------------------------------------- Coding
    ("python", "COD", 4), ("java", "COD", 4), ("c++", "COD", 4), ("cpp", "COD", 4), ("javascript", "COD", 4),
    ("typescript", "COD", 4), ("kotlin", "COD", 4), ("c#", "COD", 4), ("golang", "COD", 4), ("rust", "COD", 4),
    ("re:(?<![a-z0-9+#.])c(?![a-z0-9+#.])", "COD", 3.5),
    ("pandas", "COD", 5), ("numpy", "COD", 5), ("flask", "COD", 5), ("django", "COD", 5), ("react", "COD", 5),
    ("node.js", "COD", 5), ("spring boot", "COD", 5), ("fastapi", "COD", 5),
    ("re:\\b(libraries|library|api integration)\\b", "COD", 5),
    ("git", "COD", 5), ("github", "COD", 5), ("version control", "COD", 5),
    ("re:\\b(competitive programming|leetcode|codeforces|codechef|hackerrank|geeksforgeeks)\\b", "COD", 7),
    ("re:\\b(multi-?thread\\w*|concurren\\w*|parallel programming)\\b", "COD", 6.5),
    ("re:\\b(unit tests?|pytest|junit|test-driven|tdd|integration tests?)\\b", "COD", 6),
    ("re:\\btests? and ci\\b", "COD", 6),
    ("re:\\b(open-?source|merged prs?|pull requests?)\\b", "COD", 7),
    ("re:\\b(refactor\\w*)\\b", "COD", 6),
    ("re:\\b(code reviews?)\\b", "COD", 6),
    ("re:\\b(backend|back-end|rest apis?|api layer|apis?)\\b", "COD", 5),
    ("re:\\b(debug\\w*)\\b", "COD", 3),
    ("re:\\b(design patterns?)\\b", "COD", 6),
    # ---------------------------------------------------------------- DSA
    ("re:\\b(data structures?( and|&|/)? ?algorithms?|dsa)\\b", "DSA", 5),
    ("re:\\balgorithms?\\b", "DSA", 4),
    ("re:\\b(linked lists?|stacks?|queues?)\\b", "DSA", 3),
    ("re:\\b(binary search|sorting|hashing|hash ?maps?|hash tables?|two[- ]pointers?)\\b", "DSA", 4),
    ("re:\\b(trees?|binary trees?|greedy|recursion)\\b", "DSA", 5),
    ("re:\\b(heaps?|priority queues?|bst|sliding window)\\b", "DSA", 6),
    ("re:\\b(graphs?|bfs|dfs|backtracking|dynamic programming)\\b", "DSA", 7),
    ("re:\\b(dijkstra|shortest path|union[- ]find|mst|memoization)\\b", "DSA", 8),
    ("re:\\b(trie|segment tree|topological|scc)\\b", "DSA", 9),
    ("re:\\b(time|space) complexity|big-?o\\b", "DSA", 4),
    ("re:\\b(round robin|sjf|shortest job first)\\b", "DSA", 4),
    # ---------------------------------------------------------------- OOD
    ("re:\\b(object[- ]oriented|oop|ood|oops)\\b", "OOD", 4),
    ("re:\\b(classes|inheritance|polymorphism|encapsulation|abstraction)\\b", "OOD", 3),
    ("re:\\buml\\b", "OOD", 4),
    ("re:\\bsolid( principles)?\\b", "OOD", 5),
    ("re:\\b(design patterns?|factory|singleton)\\b", "OOD", 6),
    ("re:\\b(strategy|observer|decorator|builder pattern)\\b", "OOD", 7),
    ("re:\\b(low[- ]level design|lld|domain[- ]driven)\\b", "OOD", 8),
    ("re:\\bparking[- ]lot\\b", "OOD", 6),
    # ---------------------------------------------------------------- Aptitude / problem solving
    ("re:\\b(aptitude|quantitative|logical reasoning|puzzles?)\\b", "APTI", 4),
    ("re:\\b(problem[- ]solving)\\b", "APTI", 4),
    ("re:\\b(analy[sz]\\w*|analytics?|statistic\\w*|data interpretation)\\b", "APTI", 5),
    ("re:\\b(power bi|tableau|excel|dashboards?|data visuali[sz]ation)\\b", "APTI", 5),
    ("re:\\b(probability|hypothesis|a/b test\\w*|anomaly detection)\\b", "APTI", 6),
    ("re:\\b(precision/recall|precision and recall|evaluated with)\\b", "APTI", 6),
    # ---------------------------------------------------------------- Communication
    ("re:\\bcommunication\\b", "COMM", 4),
    ("re:\\b(present(ed|ing|ation|ations)?|presenting results)\\b", "COMM", 5),
    ("re:\\bnon-?technical (audience|stakeholders?)\\b", "COMM", 6.5),
    ("re:\\b(blog|write-?up|newsletter|technical writing|documentation|documented|published)\\b", "COMM", 5.5),
    ("re:\\b(mentor\\w*|teach\\w*|coach\\w*)\\b", "COMM", 5.5),
    ("re:\\b(coordinat\\w*|volunteer|logistics|stakeholders?)\\b", "COMM", 5),
    ("re:\\b(growth team|used by the \\w+ team|cross-?functional)\\b", "COMM", 5.5),
    ("re:\\b(escalations?|helpdesk|help desk|tickets?|first-level|customer|client[- ]facing)\\b", "COMM", 3.5),
    ("re:\\b(team lead|led a team|captain|leadership)\\b", "COMM", 6),
    # ---------------------------------------------------------------- AI (ML + AI-assisted engineering)
    ("re:\\b(machine learning|ml)\\b", "AI", 5),
    ("re:\\b(scikit-?learn|sklearn|logistic regression|regression|classification|clustering)\\b", "AI", 5),
    ("re:\\b(feature engineering|churn[- ]prediction|model training)\\b", "AI", 6),
    ("re:\\b(recommendation (engine|system)s?|collaborative filtering)\\b", "AI", 6),
    ("re:\\b(deep learning|neural network\\w*|pytorch|tensorflow|nlp|computer vision)\\b", "AI", 7),
    ("re:\\b(llm|langchain|rag|prompt\\w*|copilot|chatgpt|generative ai|openai|ai[- ]assisted)\\b", "AI", 6),
    ("re:\\b(a/b test\\w*|statistics)\\b", "AI", 4),
    # ---------------------------------------------------------------- DevOps & Cloud
    ("re:\\b(linux|unix|shell|bash|command line|cli)\\b", "CLOUD", 3),
    ("docker", "CLOUD", 4), ("re:\\bcontainer(s|ized|ization|isation)?\\b", "CLOUD", 4),
    ("re:\\b(kubernetes|k8s|helm)\\b", "CLOUD", 6),
    ("re:\\b(aws|azure|gcp|google cloud|cloud)\\b", "CLOUD", 4),
    ("re:\\b(ci/cd|ci-cd|cicd|github actions|jenkins|gitlab ci|\\bci\\b)\\b", "CLOUD", 4.5),
    ("re:\\b(terraform|cloudformation|infrastructure as code)\\b", "CLOUD", 5),
    ("re:\\b(monitoring (tools|dashboards?)|logging (and|&) monitoring|observability|grafana|prometheus|alerting)\\b", "CLOUD", 5),
    ("re:\\b(deploy\\w*)\\b", "CLOUD", 4),
    ("re:\\b(sre|incident management|auto-?scaling)\\b", "CLOUD", 8),
    # ---------------------------------------------------------------- SQL & design
    ("re:\\b(sql|mysql|postgres\\w*|sqlite|oracle db|mariadb|sql server)\\b", "SQL", 4),
    ("re:\\b(joins?|group by|subquer\\w*|crud)\\b", "SQL", 4),
    ("re:\\b(normali[sz]\\w*|schema|er diagram|foreign keys?|stored procedures?)\\b", "SQL", 5),
    ("re:\\b(index(es|ing)?|query optimi[sz]\\w*|transactions?|acid)\\b", "SQL", 6),
    ("re:\\b(database design|execution plans?|denormali[sz]\\w*)\\b", "SQL", 7),
    ("re:\\b(sharding|partitioning|replication)\\b", "SQL", 8),
    ("re:\\b(mongodb|nosql|dynamodb|cassandra)\\b", "SQL", 4),
    ("re:\\b(extraction)\\b", "SQL", 4),
    # ---------------------------------------------------------------- Software engineering
    ("re:\\b(sdlc|agile|scrum|kanban)\\b", "SWE", 5),
    ("re:\\b(unit tests?|testing|tests|test cases?|qa)\\b", "SWE", 4.5),
    ("re:\\b(ci|continuous integration)\\b", "SWE", 5.5),
    ("re:\\b(code reviews?|clean code|refactor\\w*)\\b", "SWE", 6),
    ("re:\\b(git|version control|github)\\b", "SWE", 4),
    ("re:\\b(apis?|rest|backend|back-end)\\b", "SWE", 5),
    ("re:\\b(microservices?)\\b", "SWE", 7),
    ("re:\\b(shipped|production|end-to-end|rate[- ]limiter)\\b", "SWE", 6),
    ("re:\\b(open-?source|merged prs?)\\b", "SWE", 6),
    ("re:\\b(jira|ticketing( tools)?|servicenow)\\b", "SWE", 3.5),
    ("re:\\b(requirements?)\\b", "SWE", 4),
    ("re:\\b(technical debt|distributed systems?)\\b", "SWE", 8),
    ("re:\\b(pipeline|pipelines)\\b", "SWE", 4.5),
    ("re:\\b(software engineering)\\b", "SWE", 5),
    # ---------------------------------------------------------------- System design
    ("re:\\bsystem design\\b", "SYSD", 5),
    ("re:\\b(scalab\\w*|horizontally[- ]scalable|horizontal scaling)\\b", "SYSD", 5.5),
    ("re:\\b(distributed|distributed systems?|fault[- ]toleran\\w*)\\b", "SYSD", 6.5),
    ("re:\\b(pub-?sub|message queues?|kafka|rabbitmq|event-driven)\\b", "SYSD", 6),
    ("re:\\b(cach(e|es|ed|ing)|redis|memcached)\\b", "SYSD", 5),
    ("re:\\b(load balanc\\w*)\\b", "SYSD", 5),
    ("re:\\b(microservices?|api gateway)\\b", "SYSD", 6),
    ("re:\\b(architecture diagrams?|architecture)\\b", "SYSD", 4),
    ("re:\\b(url[- ]shorten\\w*)\\b", "SYSD", 5),
    ("re:\\b(sharding|cap theorem|consistent hashing|high availability)\\b", "SYSD", 7.5),
    ("re:\\b(rate[- ]limiter|notification service)\\b", "SYSD", 5),
    ("re:\\b(real-?time)\\b", "SYSD", 5),
    ("re:\\b(chat backend|chat)\\b", "SYSD", 4),
    ("re:\\b(workers?|queue-based)\\b", "SYSD", 4.5),
    # ---------------------------------------------------------------- Networking
    ("re:\\b(computer networks?|networking|networks?)\\b", "NETW", 4),
    ("re:\\b(tcp|udp|http|https|dns|dhcp|ip address\\w*|sockets?|websockets?)\\b", "NETW", 4),
    ("re:\\b(cisco|ccna)\\b", "NETW", 3.5),
    ("re:\\b(routing|switching|vlans?|subnet\\w*)\\b", "NETW", 5),
    ("re:\\b(firewalls?|nat|load balanc\\w*|vpn)\\b", "NETW", 6),
    # ---------------------------------------------------------------- Operating systems
    ("re:\\b(operating systems?|os)\\b", "OS", 4),
    ("re:\\b(linux|unix)\\b", "OS", 3.5),
    ("re:\\b(process(es)? scheduling|cpu scheduling|scheduling algorithms?|round robin|sjf)\\b", "OS", 4.5),
    ("re:\\b(multi-?thread\\w*|threads?|concurren\\w*)\\b", "OS", 6),
    ("re:\\b(deadlocks?|semaphores?|mutex\\w*|synchroni[sz]ation)\\b", "OS", 5),
    ("re:\\b(virtual memory|paging|memory management|page replacement)\\b", "OS", 5),
    ("re:\\b(kernel|system calls?)\\b", "OS", 7),
    ("re:\\b(os-level)\\b", "OS", 5),
]


def _compile(pattern: str) -> "re.Pattern[str]":
    if pattern.startswith("re:"):
        return re.compile(pattern[3:])
    return re.compile(r"(?<![a-z0-9+#])" + re.escape(pattern) + r"(?![a-z0-9+#])")


CUES: List[Tuple["re.Pattern[str]", str, float]] = [(_compile(p), c, t) for p, c, t in _RAW]

# Words that make a claim weaker / stronger. Matched on the unit the cue appears in.
HEDGE_RE = re.compile(
    r"\b(basic|basics|beginner|introductory|intro|fundamentals?|foundational|exposure|exposed|familiar\w*|"
    r"learning|coursework|elementary|rudimentary|limited|theoretical)\b")
STRONG_RE = re.compile(
    r"\b(national|winner|won|open-?source|merged|advanced|expert|led|architected|optimi[sz]ed)\b")

# Action verbs -> Bloom depth (highest match wins). 'applied' = any of AP and above.
BLOOM_VERBS = {
    5: re.compile(r"\b(designed|architected|created|invented|founded|launched|devised|engineered)\b"),
    4: re.compile(r"\b(evaluated|optimi[sz]ed|benchmarked|reviewed|validated|measured|compared|critiqued)\b"),
    3: re.compile(r"\b(analy[sz]ed|analy[sz]ing|debugged|diagnosed|troubleshoot\w*|investigated|detected|"
                  r"anomaly|tested|resolved)\b"),
    2: re.compile(r"\b(built|implemented|developed|shipped|used|wrote|solved|ran|handled|contributed|applied|"
                  r"coordinated|mentored|presented|simulated|published|deployed|configured|managed|led|"
                  r"worked|created|finalist|winner|won|participated|integrated|automated|maintained|"
                  r"extracted|modelled|modeled|completed|delivered|performed|ranked|secured|achieved)\b"),
}
CU_RE = HEDGE_RE

# "350+ problems solved" style volume claims.
VOLUME_RE = re.compile(r"(\d{1,5})\s*\+?\s*(?:problems?|questions?|challenges?)\b")
CP_CONTEXT_RE = re.compile(r"\b(competitive|leetcode|codeforces|codechef|hackerrank|platforms?|problems?)\b")
