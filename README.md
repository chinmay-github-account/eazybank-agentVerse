# eazybank-agentVerse
AgentVerse- AI-Driven Customer Engagement for EazyBank
![image](https://github.com/user-attachments/assets/e005fb2c-1287-4123-b22e-81de135978ea)

Testing Instructions: EazyBank AgentVerse
-----------------------------------------------

Access:
---------
Open your web browser and navigate to: https://eazybank.flywithcloud.xyz/ 
(Hosted in GCP, us-central1 region)

Setup:
-------
Built using Agent Development Kit and Python 3.11.

Basic Interaction:
--------------------
Start Conversation: Enter a simple greeting like "Hi" to initiate the conversation.

Account Application Status:
-------------------------------
Enter: "I have recently applied for a savings account at EazyBank. I want to know the status for my application."
The agent will prompt you for your registered mobile number.
Use the following test mobile numbers: 2016166576, 2016166577, 2016166578, 2016166579, 2016166580

Note that,
2016166576 & 2016166580: Account application has been approved. Verify the displayed account details (number, balance, credit card).

2016166577, 2016166578, 2016166579: Account application has been rejected. Verify the displayed rejection reason.

Rejection Details: After receiving a rejection reason, ask for more details (e.g., "Why was my application rejected?"). Verify the detailed explanation provided.

Human Agent Handoff:
--------------------------
At any point, you can ask to speak to a human agent (e.g., "I want to speak to a human agent"). Verify that the application indicates you are being transferred.

Market Insights:
--------------------
Ask about EazyBank's market performance (e.g., "How is EazyBank performing in the market?", "What is EazyBank's stock price?"). Verify that the agent provides the latest stock price and relevant market news.

Expected Outcomes:
------------------------
Smooth transitions between AI agents.
Accurate account application status retrieval.
Clear and detailed explanations for rejection reasons.
Successful human agent handoff indication.
Correct and up-to-date market insights information.
