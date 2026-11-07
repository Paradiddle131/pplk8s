-- Written by probes/331_graph_measures.py from the project's manifest.
CREATE SCHEMA IF NOT EXISTS bet_graph OPTIONS (location = 'US');

CREATE OR REPLACE PROPERTY GRAPH bet_graph.metrics
  NODE TABLES (
    silver.applications AS applications
      KEY (candidate_id)
      PROPERTIES (candidate_id, applied_date, channel, current_stage, days_to_hire, hired_date, role, MEASURE(COUNT(candidate_id)) AS applications, MEASURE(COUNT(CASE WHEN (current_stage = 'hired') THEN candidate_id END)) AS hires, MEASURE(AVG(CASE WHEN (current_stage = 'hired') THEN days_to_hire END)) AS time_to_hire_days),
    silver.bookings AS bookings
      KEY (booking_id)
      PROPERTIES (booking_id, amount, booked_date, MEASURE(SUM(amount)) AS booking_value_eur, MEASURE(COUNT(booking_id)) AS bookings),
    silver.call_signals AS call_signals
      KEY (transcript_id)
      PROPERTIES (transcript_id, call_date, endpoint, next_step, objection, prompt_version, sentiment, topic, MEASURE(COUNT(transcript_id)) AS calls_labelled, MEASURE(COUNT(CASE WHEN (objection <> 'none') THEN transcript_id END)) AS calls_with_objection, MEASURE(SAFE_DIVIDE(AGG(calls_with_objection), NULLIF(AGG(calls_labelled), 0))) AS objection_rate, MEASURE(COUNT(CASE WHEN (sentiment = 'positive') THEN transcript_id END)) AS positive_calls, MEASURE(SAFE_DIVIDE(AGG(positive_calls), NULLIF(AGG(calls_labelled), 0))) AS positive_sentiment_share),
    silver.campaigns AS campaigns
      KEY (campaign_id)
      PROPERTIES (campaign_id, channel, market, name),
    silver.customer_actions AS customer_actions
      KEY (event_id)
      PROPERTIES (event_id, action_type, channel, customer_id, event_date, session_id, MEASURE(COUNT(DISTINCT customer_id)) AS acting_customers, MEASURE(COUNT(DISTINCT case when action_type = 'add_to_cart' then session_id end)) AS cart_sessions, MEASURE(COUNT(DISTINCT case when action_type = 'checkout' then session_id end)) AS checkout_sessions, MEASURE(COUNT(event_id)) AS customer_actions, MEASURE(COUNT(DISTINCT CASE WHEN (action_type = 'page_view') THEN session_id END)) AS site_sessions),
    silver.customers AS customers
      KEY (customer_id)
      PROPERTIES (customer_id, country, signup_date, MEASURE(COUNT(customer_id)) AS signups),
    silver.leads AS leads
      KEY (lead_id)
      PROPERTIES (lead_id, country, created_date, MEASURE(COUNT(lead_id)) AS leads),
    silver.orders AS orders
      KEY (order_id)
      PROPERTIES (order_id, amount, currency, customer_id, order_date, status, MEASURE(SAFE_DIVIDE(AGG(orders_cancelled), NULLIF(AGG(orders_total), 0))) AS cancellation_rate, MEASURE(COUNT(DISTINCT CASE WHEN (status <> 'cancelled') THEN customer_id END)) AS customers_distinct, MEASURE(COUNT(CASE WHEN (status = 'cancelled') THEN order_id END)) AS orders_cancelled, MEASURE(COUNT(order_id)) AS orders_total, MEASURE(SUM(CASE WHEN (status <> 'cancelled') THEN amount END)) AS revenue_eur),
    silver.outreach_messages AS outreach_messages
      KEY (message_id)
      PROPERTIES (message_id, channel, first_replied_ts, sent_date, MEASURE(COUNT(first_replied_ts)) AS messages_replied, MEASURE(COUNT(message_id)) AS messages_sent, MEASURE(SAFE_DIVIDE(AGG(messages_replied), NULLIF(AGG(messages_sent), 0))) AS reply_rate),
    silver.outreach_replies AS outreach_replies
      KEY (reply_id)
      PROPERTIES (reply_id, partner_id, replied_date, MEASURE(COUNT(DISTINCT partner_id)) AS partners_engaged, MEASURE(COUNT(reply_id)) AS replies),
    silver.partners AS partners
      KEY (partner_id)
      PROPERTIES (partner_id, country, partner_type),
    silver.returns AS returns
      KEY (return_id)
      PROPERTIES (return_id, amount, order_date, reason, return_date, MEASURE(COUNT(return_id)) AS returns_count, MEASURE(SUM(amount)) AS returns_eur, MEASURE(COUNT(return_id)) AS returns_on_order_date)
  )
  EDGE TABLES (
    silver.bookings AS bookings_to_leads
      KEY (booking_id)
      SOURCE KEY (booking_id) REFERENCES bookings (booking_id)
      DESTINATION KEY (lead_id) REFERENCES leads (lead_id),
    silver.bookings AS bookings_to_campaigns
      KEY (booking_id)
      SOURCE KEY (booking_id) REFERENCES bookings (booking_id)
      DESTINATION KEY (campaign_id) REFERENCES campaigns (campaign_id),
    silver.call_signals AS call_signals_to_customers
      KEY (transcript_id)
      SOURCE KEY (transcript_id) REFERENCES call_signals (transcript_id)
      DESTINATION KEY (customer_id) REFERENCES customers (customer_id),
    silver.customer_actions AS customer_actions_to_customers
      KEY (event_id)
      SOURCE KEY (event_id) REFERENCES customer_actions (event_id)
      DESTINATION KEY (customer_id) REFERENCES customers (customer_id),
    silver.leads AS leads_to_campaigns
      KEY (lead_id)
      SOURCE KEY (lead_id) REFERENCES leads (lead_id)
      DESTINATION KEY (campaign_id) REFERENCES campaigns (campaign_id),
    silver.orders AS orders_to_customers
      KEY (order_id)
      SOURCE KEY (order_id) REFERENCES orders (order_id)
      DESTINATION KEY (customer_id) REFERENCES customers (customer_id),
    silver.outreach_messages AS outreach_messages_to_partners
      KEY (message_id)
      SOURCE KEY (message_id) REFERENCES outreach_messages (message_id)
      DESTINATION KEY (partner_id) REFERENCES partners (partner_id),
    silver.outreach_replies AS outreach_replies_to_outreach_messages
      KEY (reply_id)
      SOURCE KEY (reply_id) REFERENCES outreach_replies (reply_id)
      DESTINATION KEY (message_id) REFERENCES outreach_messages (message_id),
    silver.outreach_replies AS outreach_replies_to_partners
      KEY (reply_id)
      SOURCE KEY (reply_id) REFERENCES outreach_replies (reply_id)
      DESTINATION KEY (partner_id) REFERENCES partners (partner_id),
    silver.returns AS returns_to_orders
      KEY (return_id)
      SOURCE KEY (return_id) REFERENCES returns (return_id)
      DESTINATION KEY (order_id) REFERENCES orders (order_id),
    silver.returns AS returns_to_customers
      KEY (return_id)
      SOURCE KEY (return_id) REFERENCES returns (return_id)
      DESTINATION KEY (customer_id) REFERENCES customers (customer_id)
  );
