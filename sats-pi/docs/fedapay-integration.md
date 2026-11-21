# Intégration FedaPay (payout)

Source : documentation FedaPay, relue le 17 novembre 2026 (docs.fedapay.com).

## Ce qui est confirmé
- Bases : sandbox-api.fedapay.com/v1 et api.fedapay.com/v1, authentification Bearer (clé secrète).
- POST /payouts : amount (entier), currency {iso}, mode, customer {firstname, lastname, phone_number {number, country}}, merchant_reference (unique, jamais réutilisée).
- PUT /payouts/start : corps = tableau [{id}].
- GET /payouts/{id} : statuts pending, started, processing, sent, failed.
- Opérateurs de payout cités : MTN Bénin, Moov Bénin, MTN Côte d'Ivoire, Moov Togo, Togocel.
- Le payout est activé sur demande (support@fedapay.com) et paie depuis le solde du compte FedaPay.
- FedaPay encaisse dans 8 pays (Bénin, Burkina Faso, Côte d'Ivoire, Guinée, Mali, Niger, Sénégal, Togo), mais le payout n'est confirmé que pour Bénin, Côte d'Ivoire, Togo.

## À vérifier avant la démo (sandbox)
1. Valeurs exactes du champ `mode` par opérateur (variable FEDAPAY_MODES). Défaut : "mobile_money".
2. Format du numéro local (8 chiffres au Bénin, comme dans l'exemple de la doc ? 10 chiffres ?) et code pays (minuscules à la création).
3. Enveloppe des réponses (gérée par `_unwrap`).
4. Pas d'événement webhook de payout documenté : le backend interroge le statut.
5. Tarif réel des payouts (remplace PAYOUT_FEE_PCT = 0,8 %, provisoire).

## À demander à FedaPay par écrit
- Activation des payouts sur le compte, et pays/opérateurs couverts réellement.
- Acceptation d'une activité adossée à du Bitcoin Lightning (conversion des sats reçus). Les conditions de FedaPay sur ce point n'ont pas été vérifiées.
- Plafonds par transaction et par jour, délais.

## Flux de trésorerie
FedaPay paie depuis son solde : il faut un solde FedaPay approvisionné (float). Les sats reçus doivent être vendus puis le produit en FCFA versé sur le compte FedaPay. Un solde insuffisant fait échouer le payout (statut PAYOUT_FAILED, reprise manuelle).
