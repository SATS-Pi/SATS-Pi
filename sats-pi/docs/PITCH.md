# SATS-PI : pitch de 3 minutes

*Receive sats from the world, spend FCFA at home.*

Dakar Bitcoin Days, hackathon Bitcoin. Les chiffres marqués (vérifier) sont à confirmer avant de monter sur scène.

---

## 0:00 – 0:30 · Accroche

« Un Béninois à Paris veut envoyer 20 000 francs à sa mère à Cotonou.

Avec Western Union ou MoneyGram, il paie entre 5 et 8 % de frais et sa mère attend un à deux jours (vérifier). Avec Bitcoin Lightning, l'argent traverse la planète en deux secondes pour une fraction de centime.

Mais au marché de Dantokpa, personne ne paie en sats. Ils veulent du MoMo. »

## 0:30 – 1:00 · Le dernier kilomètre

« Ce dernier kilomètre existe désormais.

Depuis aujourd'hui, 2 novembre, tous les transferts de monnaie électronique entre particuliers dans l'UEMOA passent obligatoirement par PI-SPI, la plateforme de paiement instantané de la BCEAO. Les opérateurs sont interconnectés, et envoyer jusqu'à 8 000 francs par jour est gratuit.

PI-SPI existe depuis septembre 2025. Ce qui change aujourd'hui, c'est qu'il devient le rail unique. Le Bitcoin règle la partie internationale, PI-SPI règle la partie locale. Il manquait le pont entre les deux. »

## 1:00 – 2:15 · Démo en direct

« Voici SATS-PI. »

1. Ouvrir la page. Saisir le numéro MoMo de quelqu'un dans la salle, **avec son accord**, et un montant, par exemple 2 000 F.
2. Montrer le devis : *« Voilà exactement ce que la famille reçoit, et ce que l'expéditeur paie. Pas de frais cachés. »*
3. Générer le lien. Le QR Lightning s'affiche.
4. Un volontaire paie avec son wallet Lightning (Wallet of Satoshi, Phoenix ou Blink).
5. Le statut passe à « Envoyé ».

**Phrase à dire, sans la cacher :** *« Le rail Lightning est réel. Le rail PI-SPI est ici en sandbox, parce que l'accès de production à l'API Business exige un agrément que nous n'avons pas encore. Le code de sortie est prêt à être branché sur l'API Ecobank, seule API Business homologuée au Bénin à fin septembre. »*

**Règle d'or :** n'annonce « le SMS MoMo arrive » que si la sortie est réellement branchée. Un jury technique remarquera tout de suite une simulation présentée comme réelle, et c'est ce qui coule une équipe. Prépare toujours une vidéo de secours d'un envoi qui a vraiment fonctionné, pour le cas où le réseau de la salle lâche.

## 2:15 – 2:45 · Pourquoi ça tient

- **L'utilisateur final ne gère pas de crypto.** Celui qui reçoit voit du MoMo, celui qui envoie utilise un wallet qu'il a déjà.
- **La conformité est dans le modèle.** SATS-PI est la couche technique, au-dessus d'un partenaire agréé qui porte la licence, le KYC et le float en FCFA.
- **Le modèle est calculable :** 1 % de marge pour nous, plus les frais PI-SPI en transparence (0 à 0,8 % au-delà du seuil gratuit). Soit environ 2 % au maximum pour l'expéditeur, contre 5 à 8 % ailleurs (vérifier).

## 2:45 – 3:00 · Clôture

« On ne veut pas que les Africains utilisent Bitcoin.
On veut que Bitcoin utilise PI-SPI,
pour que les Africains paient moins cher. »

---

## Questions probables du jury

| Question | Réponse courte |
|---|---|
| Qui détient le float en FCFA entre la réception des sats et l'envoi ? | Un partenaire de trésorerie agréé ou un teneur de marché. Le MVP simule ce compte, la production le confie à l'établissement partenaire. |
| Avez-vous une licence ? | Non, et nous ne prétendons pas en avoir. SATS-PI est une couche technique au-dessus d'un établissement agréé. |
| Et si le cours bouge pendant la facture ? | Le taux est figé 15 minutes. Le risque sur cette fenêtre est couvert par la marge. |
| Et si PI-SPI échoue après réception des sats ? | Le paiement est marqué en échec, jamais perdu. Une reprise manuelle est possible, sans double paiement grâce à la clé d'idempotence. |
| Pourquoi pas directement Orange Money ou MTN ? | Passer par PI-SPI donne un seul point d'intégration pour tous les opérateurs de l'UEMOA, au lieu d'une intégration par opérateur. |
| Les plafonds ? | Plafond du MVP : 100 000 F. Les plafonds officiels sont à citer uniquement avec source. |

## À vérifier avant de monter sur scène

- Les 5 à 8 % de frais et « 1 à 2 jours » pour Western Union et MoneyGram (source récente).
- Le chiffre de 12 milliards de dollars de transferts vers l'UEMOA (source et année).
- Le montant exact des frais Lightning que tu annonces.
- Que le wallet du volontaire a vraiment des sats avant de monter.
