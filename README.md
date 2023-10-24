# Legifrance -> GitHub
The goal of this project is to convert LegiFrance into a github project.
Our goal is to make the law easier to navigate (with a focus on people familiar
with GitHub / GitLab).

## APIs
- [LegiFrance](https://piste.gouv.fr/index.php?option=com_apiportal&view=apitester&usage=api&apitab=tests&apiName=L%C3%A9gifrance&apiId=7daab368-e9f3-4511-989d-aba63907eef7&managerId=2&type=rest&apiVersion=2.0.0&Itemid=402&swaggerVersion=2.0&lang=fr)
- Data Reused under [Open License V2](https://www.etalab.gouv.fr/wp-content/uploads/2017/04/ETALAB-Licence-Ouverte-v2.0.pdf)
- The last download can be found under [legifrance/README.md](https://github.com/LexHub-project/legifrance/blob/main/README.md)
- The scope of this project is to see how / if we can rebuild legal codes in a different format. It is provided without any guarantees and waranties. It should not be used without double checking primary sources.

## Algorithm
TODO

## Data Model
The LegiFrance data model doesn't map 1-1 to git/GitHub. A few decisions had to
be made:
- Main should track the current law
- Future changes, already approved by law are tracked in PRs
- Changes under discussion are tracked in PRs

TODO: differenciate PRs
