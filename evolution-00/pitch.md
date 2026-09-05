# Evolution 0 — System Pitch

## Graduate Application Identity-Assurance and Triage System

### User and Problem

The main users of this system will be **graduate admissions staffs**. The problem I want to work on is the time spent dealing with suspicious or "ghost" applications.

From my conversations with graduate admissions staffs, I learned that some ghost applications use the identities of real people. This can make them difficult to identify. Staff may have to spend time reading documents, checking information that does not match, communicating with applicants, and asking other people in the university for help. If the application continues further, program faculty and other departments may also spend time working on it.

The goal of my system is not to decide that someone is committing fraud. The goal is to help staff identify applications that may need more verification earlier in the process. If an application has enough evidence to continue normally, it can move forward. If something is unclear or does not match, the application can be sent for more verification.

### Proposed System

The system will look at information that it is allowed to use from an application. It can look for things that do not match or situations where more information may be needed.

Not every decision needs AI. If the university already has a clear rule for something, I would rather use a **deterministic rule**. This means the same rule is followed whenever the same condition occurs.

I would use **agentic reasoning** when the situation is not as clear. For example, the system may need to look at different pieces of information, decide which approved tool or verification step to use, look at the result, and then decide what to do next.

The system can keep track of the case, gather allowed information, use approved tools, and give staff a summary of what it found. It can then recommend that the application continue normally or be sent for more verification.

The system will **not automatically reject an applicant or declare someone a fraudster**. Important final decisions will remain with the appropriate university staff or an approved identity-verification provider.

### Why This Project Fits the Semester

This project gives me room to use the different things we will learn during the semester.

The **agent loop** can allow the system to receive information, reason about what to do, take an action, look at the result, and continue until it reaches a reason to stop.

**Patterns and orchestration** can help organize the steps the system follows.

**Tools and MCP** can allow the system to use approved or simulated services to get information it needs.

**Context and memory** can help the system keep track of important information about an application while it is working on the case.

Later, I can test **multi-agent systems** to see if using more than one agent makes the system better. For example, one agent could perform an assessment while another checks its work.

**Evaluation** will help me test how well the system works. I can measure things such as how often it incorrectly flags a legitimate application, how often it misses a suspicious application, how consistent its results are, and how much time or cost is involved.

**Governance and human oversight** will help make sure the AI does not have authority over important final decisions.

Finally, **deployment and runtime** will allow me to test how the completed system can actually run while keeping records of what it did and allowing people to review its actions.

### Biggest Risk

The biggest risk is incorrectly flagging a legitimate applicant.

If the system makes that mistake, a real applicant could be asked to complete unnecessary verification, their application could be delayed, staff could have more work to do, or the applicant could decide not to continue with WT.

The opposite mistake is also important. If the system fails to identify a suspicious application, that application may continue further into the process and take more time from admissions staff, program faculty, and other university departments.

Because of this, I do not want the AI to make the final decision. The system should provide evidence and help with the process, while important decisions remain with people.

## PEAS Specification

### Performance Measure — Evaluation and Feedback

I will measure whether the system helps reduce the amount of unnecessary work caused by suspicious applications without creating too many problems for legitimate applicants. I can measure **false positives, false negatives, consistency, quality of evidence, staff effort, cost, and time**.

**Nine-component mapping:** Evaluation and Feedback.

### Environment — Runtime and Operations

The environment is the graduate application process. It includes application information, submitted documents, verification information, university rules, and approved or simulated services that the system may use.

**Nine-component mapping:** Runtime and Operations.

### Actuators — Tools and Orchestration

The system can use approved tools to check information, gather allowed evidence, request another verification step, send a case for additional review, create a summary for staff, or allow the application to continue through the normal process.

**Nine-component mapping:** Tools and Orchestration.

### Sensors — Perception

The system receives information from the application, submitted documents, information that does not match, verification results, and the current status of the application.

**Nine-component mapping:** Perception.