**Cheat-Sheet Git — Commandes principales**

**Configuration**

```
git config --global user.name "TonNom"
git config --global user.email "ton@mail.com"
```

**État du dépôt**

```
git status
```

**Ajout / Commit**

```
git add .
git add fichier
git commit -m "Message"
```

**Historique**

```
git log --oneline
git log
```

**Voir un commit**

```
git show <ID>
```

**Retour en arrière**

```
git checkout <ID>
git reset --hard <ID>
git revert <ID>
```

**Branches**

```
git branch
git branch nouvelle-branche
git checkout nouvelle-branche
git checkout -b nouvelle-branche
git merge nouvelle-branche
```

**Stash**

```
git stash
git stash list
git stash pop
git stash apply
```

**Remote**

```
git remote -v
git fetch
git pull
git push
```

**Synchronisation**

```
git pull origin master
git push origin master
```
