FROM maven:3.9-eclipse-temurin-{{ runtime_version }}

WORKDIR /app

COPY pom.xml ./
COPY src ./src

CMD ["mvn", "-q", "spring-boot:run"]
